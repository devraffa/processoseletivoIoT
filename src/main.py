import machine
import time
from ssd1306 import SSD1306_I2C
import os

# configuração de pinos, na placa esp32

TRIG_PIN = 5
ECHO_PIN = 18
LED_R_PIN = 13
LED_G_PIN = 12
LED_B_PIN = 14
BUZZER_PIN = 27
I2C_SDA_PIN = 21
I2C_SCL_PIN = 22

trig = machine.Pin(TRIG_PIN, machine.Pin.OUT)
echo = machine.Pin(ECHO_PIN, machine.Pin.IN)
led_r = machine.Pin(LED_R_PIN, machine.Pin.OUT)
led_g = machine.Pin(LED_G_PIN, machine.Pin.OUT)
led_b = machine.Pin(LED_B_PIN, machine.Pin.OUT)
buzzer = machine.PWM(machine.Pin(BUZZER_PIN))
buzzer.freq(1000)   # 1000 hz de frequência para o buzzer
buzzer.duty(0)      # começa desligado

# configuração de display oled
i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA_PIN), scl=machine.Pin(I2C_SCL_PIN), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

# todas as distancias em centimetros
DIST_CRITICA = 20.0  
DIST_ATENCAO = 60.0  
DIST_MAXIMA = 150.0 

ESTADO_INATIVO = 0
ESTADO_SEGURO = 1    # verde
ESTADO_ATENCAO = 2   # amarelo
ESTADO_PERIGO = 3    # vermelho 

# variaveis de controle
estado_atual = -1 # começa em -1 para forçar a primeira atualização do OLED
ultimo_tempo_medicao = 0
ultima_dist_impressa = -100
intervalo_medicao = 100 # lê a cada 100ms


# lógica de registro de eventos (log)

ARQUIVO_LOG = "eventos.log"

def registrar_evento(estado, distancia):
    tempo = time.ticks_ms()
    linha = f"{tempo},{estado},{distancia:.1f}\n"
    # grava no arquivo
    try:
        with open(ARQUIVO_LOG, "a") as f:
            f.write(linha)
    except OSError:
        print("Erro ao gravar log")
    # mostra também no console/terminal
    print(f"LOG: {tempo} ms - {estado} - {distancia:.1f} cm")


# funções de Hardware

def ler_distancia():
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    duracao = machine.time_pulse_us(echo, 1, 30000) 
    if duracao < 0: return -1
    return (duracao * 0.0343) / 2

def atualizar_atuadores(r, g, b, buz):
    # como o LED é ânodo comum, nível 0 acende, 1 apaga.
    led_r.value(not r)
    led_g.value(not g)
    led_b.value(not b)
    # o buzzer é via PWM
    if buz:
        buzzer.duty(512)   # 50% de duty cycle (volume médio)
    else:
        buzzer.duty(0)     # desliga

def atualizar_oled(estado_nome, distancia):
    oled.fill(0) # limpa a tela
    oled.text("RADAR INDUSTRIAL", 0, 0)
    oled.text("----------------", 0, 10)
    
    if estado_nome == "INATIVO":
        oled.text("MODO STANDBY", 15, 30)
        oled.text("Fora de Alcance", 5, 45)
    else:
        oled.text("Dist:", 0, 30)
        oled.text(f"{distancia:.1f} cm", 45, 30)
        oled.text("Status:", 0, 45)
        oled.text(estado_nome, 60, 45)
        
    oled.show() # envia as alterações para o display


# Lógica Principal (Máquina de Estados)

def maquina_de_estados():
    global estado_atual, ultimo_tempo_medicao, ultima_dist_impressa
    tempo_atual = time.ticks_ms()

    # execução assíncrona baseada em tempo, sem usar delays que bloqueiam o processador
    if time.ticks_diff(tempo_atual, ultimo_tempo_medicao) >= intervalo_medicao:
        dist = ler_distancia()
        ultimo_tempo_medicao = tempo_atual
        
        # só atualiza a tela se a distância mudar mais de 0.5cm, para evitar flickering 
        precisa_atualizar_tela = abs(dist - ultima_dist_impressa) > 0.5
        
        # lógica de falha / inatividade
        if dist < 0 or dist > DIST_MAXIMA:
            if estado_atual != ESTADO_INATIVO:
                estado_atual = ESTADO_INATIVO
                atualizar_atuadores(0, 0, 0, 0)
                atualizar_oled("INATIVO", 0)
                print("SISTEMA INATIVO - Economia de Energia")
            return

        # lógica de zonas de risco
        if dist > DIST_ATENCAO:
            if estado_atual != ESTADO_SEGURO or precisa_atualizar_tela:
                estado_atual = ESTADO_SEGURO
                ultima_dist_impressa = dist
                atualizar_atuadores(0, 1, 0, 0) # verde
                atualizar_oled("SEGURO", dist)
                
        elif DIST_CRITICA < dist <= DIST_ATENCAO:
            if estado_atual != ESTADO_ATENCAO or precisa_atualizar_tela:
                estado_atual = ESTADO_ATENCAO
                ultima_dist_impressa = dist
                atualizar_atuadores(1, 1, 0, 0) # amarelo (vermelho + verde)
                atualizar_oled("ATENCAO!", dist)
                registrar_evento("ATENCAO", dist)   # adicionando ao log de eventos
                
        else:
            if estado_atual != ESTADO_PERIGO or precisa_atualizar_tela:
                estado_atual = ESTADO_PERIGO
                ultima_dist_impressa = dist
                atualizar_atuadores(1, 0, 0, 1) # vermelho + buzzer
                atualizar_oled("PERIGO!!!", dist)
                registrar_evento("PERIGO", dist)   # adicionando ao log de eventos


# Loop de Execução

oled.fill(0)
oled.text("Iniciando...", 20, 30)
oled.show()
time.sleep(1) # único delay permitido, apenas no boot do sistema

# FLAG DE AMBIENTE: Implementei uma flag para diferenciar entre modo de teste (CI/CD) e modo de produção/simulação real-time.
# False = Modo CI/CD (GitHub Actions) - Execução com tempo limite para testes.
# True  = Modo Produção/Simulação - Execução infinita (real-time).
MODO_MANUAL = False 

def modo_teste():
    print("Iniciando teste automático no Actions...")
    
    # roda a máquina de estados 15 vezes para simular o funcionamento
    # como seu intervalo é de 100ms, isso dá cerca de 1.5 segundos de simulação
    for _ in range(15):
        maquina_de_estados()
        time.sleep(0.1)
        
    print("Teste")

# Contolando o fluxo
if MODO_MANUAL:
    while True: # loop infinito para execução normal
        maquina_de_estados()
    
else:
    modo_teste()

