# verLog.py - Exibe o conteúdo do arquivo de log de eventos no console

ARQUIVO_LOG = "eventos.log"

def mostrar_log():
    try:
        with open(ARQUIVO_LOG, "r") as f:
            conteudo = f.read()
        if conteudo:
            print("=== LOG DE EVENTOS ===")
            print("(tempo_ms, estado, distancia_cm)")
            print(conteudo)
        else:
            print("Nenhum evento registrado ainda.")
    except OSError:
        print("Erro ao abrir o arquivo de log.")

# executa automaticamente ao importar
mostrar_log()