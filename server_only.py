"""
Inicialização simplificada do servidor web para uso local, útil em testes e execução apenas no navegador.

Créditos do projeto: Nostrand.
"""

#!/usr/bin/env python3
import socket
from modules.servidor_flask import criar_app
from modules.logging_config import obter_logger, registrar_etapa, configurar_logging, instalar_hook_excecoes
logger = obter_logger(__name__)
configurar_logging()
instalar_hook_excecoes()

app = criar_app()


@registrar_etapa
def get_local_ip():
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    ip = get_local_ip()
    port = 5000

    logger.info("Servidor Flask rodando | local=http://127.0.0.1:%s | rede=http://%s:%s", port, ip, port)
    logger.info("Pressione Ctrl+C para encerrar.")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
