import machine
import time
import ssd1306
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
buzzer.freq(1000)   # 1000 Hz, tom audível agradável
buzzer.duty(0)      # começa desligado

# configuração de display oled
i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA_PIN), scl=machine.Pin(I2C_SCL_PIN), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# todas em centimetros
DIST_CRITICA = 20.0  
DIST_ATENCAO = 60.0  
DIST_MAXIMA = 150.0 

ESTADO_INATIVO = 0
ESTADO_SEGURO = 1    # Verde
ESTADO_ATENCAO = 2   # Amarelo
ESTADO_PERIGO = 3    # Vermelho

# variaveis de controle
estado_atual = -1 # Começa em -1 para forçar a primeira atualização do OLED
ultimo_tempo_medicao = 0
ultima_dist_impressa = -100
intervalo_medicao = 100 # Lê a cada 100ms (10Hz)

ARQUIVO_LOG = "eventos.log"

def registrar_evento(estado, distancia):
    tempo = time.ticks_ms()
    linha = f"{tempo},{estado},{distancia:.1f}\n"
    # Grava no arquivo
    try:
        with open(ARQUIVO_LOG, "a") as f:
            f.write(linha)
    except OSError:
        print("Erro ao gravar log")
    # Mostra também no console (Serial Monitor)
    print(f"LOG: {tempo} ms - {estado} - {distancia:.1f} cm")

# ==========================================
# Funções de Hardware
# ==========================================
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
    # Como o LED é ânodo comum, nível 0 acende, 1 apaga.
    led_r.value(not r)
    led_g.value(not g)
    led_b.value(not b)
    # Buzzer via PWM
    if buz:
        buzzer.duty(512)   # 50% de duty cycle (volume médio)
    else:
        buzzer.duty(0)     # desliga

def atualizar_oled(estado_nome, distancia):
    oled.fill(0) # Limpa a tela
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
        
    oled.show() # Envia as alterações para o display

# ==========================================
# Lógica Principal (Máquina de Estados)
# ==========================================
def maquina_de_estados():
    global estado_atual, ultimo_tempo_medicao, ultima_dist_impressa
    tempo_atual = time.ticks_ms()

    # Execução Assíncrona Não-Bloqueante
    if time.ticks_diff(tempo_atual, ultimo_tempo_medicao) >= intervalo_medicao:
        dist = ler_distancia()
        ultimo_tempo_medicao = tempo_atual
        
        # Filtro: Só atualiza a tela se a distância mudar mais de 0.5cm (Evita flickering na tela)
        precisa_atualizar_tela = abs(dist - ultima_dist_impressa) > 0.5
        
        # Lógica de Falha / Inatividade
        if dist < 0 or dist > DIST_MAXIMA:
            if estado_atual != ESTADO_INATIVO:
                estado_atual = ESTADO_INATIVO
                atualizar_atuadores(0, 0, 0, 0)
                atualizar_oled("INATIVO", 0)
                print("SISTEMA INATIVO - Economia de Energia")
            return

        # Lógica de Zonas de Risco
        if dist > DIST_ATENCAO:
            if estado_atual != ESTADO_SEGURO or precisa_atualizar_tela:
                estado_atual = ESTADO_SEGURO
                ultima_dist_impressa = dist
                atualizar_atuadores(0, 1, 0, 0) # Verde
                atualizar_oled("SEGURO", dist)
                
        elif DIST_CRITICA < dist <= DIST_ATENCAO:
            if estado_atual != ESTADO_ATENCAO or precisa_atualizar_tela:
                estado_atual = ESTADO_ATENCAO
                ultima_dist_impressa = dist
                atualizar_atuadores(1, 1, 0, 0) # Amarelo (Vermelho + Verde)
                atualizar_oled("ATENCAO!", dist)
                registrar_evento("ATENCAO", dist)   # <-- LOG
                
        else:
            if estado_atual != ESTADO_PERIGO or precisa_atualizar_tela:
                estado_atual = ESTADO_PERIGO
                ultima_dist_impressa = dist
                atualizar_atuadores(1, 0, 0, 1) # Vermelho + Buzzer
                atualizar_oled("PERIGO!!!", dist)
                registrar_evento("PERIGO", dist)   # <-- LOG

# ==========================================
# Loop de Execução
# ==========================================
oled.fill(0)
oled.text("Iniciando...", 20, 30)
oled.show()
time.sleep(1) # Único delay permitido, apenas no boot do sistema

while True:
    maquina_de_estados()