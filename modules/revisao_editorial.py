"""Revisão editorial por documento; arquivos separados do texto exportável."""
from __future__ import annotations
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
import os
from threading import RLock
from uuid import uuid4
import re
from bs4 import BeautifulSoup
from .persistencia_json import ler_json, salvar_json
from .i18n import t

LOCK = RLock()
MAX_ITENS, MAX_VERSOES, MAX_HTML = 400, 40, 2_000_000


def arquivo(pasta: Path, tipo: str, numero: int) -> Path:
    if tipo not in ('livro', 'roteiro') or not 1 <= int(numero) <= 999999:
        raise ValueError(t('editorial.backend.invalid_document'))
    return Path(pasta) / 'revisao_editorial' / f'{tipo}_{int(numero)}.json'


def arquivo_versao(pasta: Path, tipo: str, numero: int, id_versao: str) -> Path:
    # IDs apenas UUID em hex: não há nomes/caminhos arbitrários recebidos do cliente.
    if not re.fullmatch(r'[0-9a-f]{32}', str(id_versao)):
        raise ValueError(t('editorial.backend.invalid_version_id'))
    base = arquivo(pasta, tipo, numero)
    return base.parent / f'{tipo}_{int(numero)}_versoes' / f'{id_versao}.html'


def salvar_html_versao(pasta, tipo, numero, id_versao, html):
    caminho = arquivo_versao(pasta, tipo, numero, id_versao)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + '.tmp')
    with temporario.open('w', encoding='utf8') as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ler(pasta: Path, tipo: str, numero: int, *, incluir_html=False) -> dict:
    with LOCK:
        obj = ler_json(arquivo(pasta, tipo, numero), {})
        if not isinstance(obj, dict): obj = {}
        dados = {'formato': 1, 'itens': obj.get('itens', []), 'versoes': obj.get('versoes', [])}
        if not isinstance(dados['itens'], list): dados['itens'] = []
        if not isinstance(dados['versoes'], list): dados['versoes'] = []
        if incluir_html:
            for item in dados['versoes']:
                if 'html' not in item:
                    caminho = arquivo_versao(pasta, tipo, numero, item['id'])
                    item['html'] = caminho.read_text('utf8') if caminho.is_file() else ''
        else:
            dados['versoes'] = [{k:v for k,v in item.items() if k != 'html'} for item in dados['versoes']]
        return dados


def _salvar(pasta, tipo, numero, dados):
    salvar_json(arquivo(pasta, tipo, numero), dados)


def campo(payload, nome, limite, obrigatorio=False):
    valor = payload.get(nome, '')
    if not isinstance(valor, str) or len(valor) > limite:
        raise ValueError(t('editorial.backend.invalid_field', campo=nome))
    if obrigatorio and not valor.strip():
        raise ValueError(t('editorial.backend.required_field', campo=nome))
    return valor


def criar_item(pasta, tipo, numero, payload):
    with LOCK:
        dados = ler(pasta, tipo, numero)
        if len(dados['itens']) >= MAX_ITENS:
            raise ValueError(t('editorial.backend.max_comments'))
        classe = payload.get('tipo')
        if classe not in ('comentario', 'sugestao'):
            raise ValueError(t('editorial.backend.invalid_type'))
        trecho = campo(payload, 'trecho', 2000, True)
        nota = campo(payload, 'nota', 4000)
        substituir = campo(payload, 'substituicao', 2000, classe == 'sugestao')
        if classe == 'comentario' and not nota.strip():
            raise ValueError(t('editorial.backend.comment_required'))
        try: inicio = int(payload.get('inicio'))
        except (TypeError, ValueError): raise ValueError(t('editorial.backend.invalid_selection')) from None
        if inicio < 0 or inicio > 15_000_000: raise ValueError(t('editorial.backend.invalid_selection'))
        item = {'id': uuid4().hex, 'tipo': classe, 'estado': 'pendente',
                'trecho': trecho, 'nota': nota, 'substituicao': substituir if classe == 'sugestao' else '',
                'inicio': inicio, 'prefixo': campo(payload, 'prefixo', 120),
                'sufixo': campo(payload, 'sufixo', 120),
                'criado_em': agora(), 'atualizado_em': agora()}
        dados['itens'].append(item)
        _salvar(pasta, tipo, numero, dados)
        return item


def alterar_item(pasta, tipo, numero, item_id, estado):
    if estado not in ('pendente', 'aceito', 'rejeitado', 'resolvido'):
        raise ValueError(t('editorial.backend.invalid_status'))
    with LOCK:
        dados = ler(pasta, tipo, numero)
        for item in dados['itens']:
            if item.get('id') != item_id: continue
            if item['tipo'] == 'comentario' and estado in ('aceito', 'rejeitado'):
                raise ValueError(t('editorial.backend.invalid_comment_status'))
            if item['tipo'] == 'sugestao' and estado == 'resolvido':
                raise ValueError(t('editorial.backend.invalid_suggestion_status'))
            item['estado'], item['atualizado_em'] = estado, agora()
            _salvar(pasta, tipo, numero, dados)
            return item
    raise FileNotFoundError('Anotação não encontrada.')


def apagar_item(pasta, tipo, numero, item_id):
    with LOCK:
        dados = ler(pasta, tipo, numero)
        resto = [x for x in dados['itens'] if x.get('id') != item_id]
        if len(resto) == len(dados['itens']): raise FileNotFoundError('Anotação não encontrada.')
        dados['itens'] = resto
        _salvar(pasta, tipo, numero, dados)



def criar_versao(pasta, tipo, numero, titulo, html, rotulo=''):
    if not isinstance(html, str) or len(html.encode('utf8')) > MAX_HTML:
        raise ValueError(t('editorial.backend.large_version'))
    if not isinstance(rotulo, str) or len(rotulo) > 120:
        raise ValueError(t('editorial.backend.invalid_label'))
    with LOCK:
        dados = ler(pasta, tipo, numero)
        digest = sha256(html.encode('utf8')).hexdigest()
        if dados['versoes'] and dados['versoes'][-1].get('hash') == digest:
            return {k:v for k,v in dados['versoes'][-1].items() if k != 'html'}
        if len(dados['versoes']) >= MAX_VERSOES:
            raise ValueError(t('editorial.backend.max_versions'))
        item = {'id':uuid4().hex, 'rotulo':rotulo.strip() or 'Versão de revisão',
                'titulo':str(titulo)[:200], 'criado_em':agora(), 'hash':digest}
        salvar_html_versao(pasta, tipo, numero, item['id'], html)
        dados['versoes'].append(item)
        _salvar(pasta, tipo, numero, dados)
        return item


def obter_versao(pasta, tipo, numero, version_id):
    for versao in ler(pasta, tipo, numero)['versoes']:
        if versao.get('id') == version_id:
            caminho = arquivo_versao(pasta, tipo, numero, version_id)
            if not caminho.is_file(): raise FileNotFoundError('Arquivo de versão não encontrado.')
            return {**versao, 'html': caminho.read_text('utf8')}
    raise FileNotFoundError('Versão não encontrada.')


def apagar_versao(pasta, tipo, numero, version_id):
    with LOCK:
        dados = ler(pasta, tipo, numero)
        resto = [x for x in dados['versoes'] if x.get('id') != version_id]
        if len(resto) == len(dados['versoes']): raise FileNotFoundError('Versão não encontrada.')
        dados['versoes'] = resto
        _salvar(pasta, tipo, numero, dados)
        arquivo_versao(pasta, tipo, numero, version_id).unlink(missing_ok=True)


def texto_html(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript']): tag.decompose()
    return soup.get_text(' ', strip=True)


def comparar(html_antigo: str, html_atual: str) -> list[dict]:
    palavras_a = re.findall(r'\S+\s*', texto_html(html_antigo))
    palavras_b = re.findall(r'\S+\s*', texto_html(html_atual))
    if len(palavras_a) + len(palavras_b) > 12000:
        raise ValueError(t('editorial.backend.large_diff'))
    resultado = []
    for op, a0, a1, b0, b1 in SequenceMatcher(None, palavras_a, palavras_b, autojunk=True).get_opcodes():
        if op in ('equal', 'replace', 'delete'):
            texto = ''.join(palavras_a[a0:a1])
            if texto: resultado.append({'tipo': 'igual' if op == 'equal' else 'removido', 'texto': texto})
        if op in ('replace', 'insert'):
            texto = ''.join(palavras_b[b0:b1])
            if texto: resultado.append({'tipo':'adicionado', 'texto':texto})
    return resultado


def importar_estado(pasta, tipo, numero, payload):
    """Restaura dados opcionais de um .gut sem alterar o texto dos documentos.

    Backups antigos não contêm este campo e continuam compatíveis.
    """
    if not isinstance(payload, dict):
        return
    itens_brutos = payload.get('itens', [])
    versoes_brutas = payload.get('versoes', [])
    if not isinstance(itens_brutos, list) or not isinstance(versoes_brutas, list):
        raise ValueError(t('editorial.backend.invalid_backup'))
    if len(itens_brutos) > MAX_ITENS or len(versoes_brutas) > MAX_VERSOES:
        raise ValueError(t('editorial.backend.large_backup'))
    itens, versoes = [], []
    for x in itens_brutos:
        if not isinstance(x, dict) or x.get('tipo') not in ('comentario', 'sugestao'):
            continue
        if x.get('estado') not in ('pendente', 'aceito', 'rejeitado', 'resolvido'):
            continue
        if not isinstance(x.get('trecho'), str) or len(x['trecho']) > 2000:
            continue
        if any(not isinstance(x.get(k, ''), str) or len(x.get(k, '')) > m
               for k,m in [('nota',4000),('substituicao',2000),('prefixo',120),('sufixo',120)]):
            continue
        try: start = int(x.get('inicio', 0))
        except (TypeError, ValueError): continue
        if not 0 <= start <= 15_000_000: continue
        itens.append({'id':uuid4().hex, 'tipo':x['tipo'], 'estado':x['estado'],
                      'trecho':x['trecho'], 'nota':x.get('nota',''),
                      'substituicao':x.get('substituicao',''), 'inicio':start,
                      'prefixo':x.get('prefixo',''), 'sufixo':x.get('sufixo',''),
                      'criado_em':str(x.get('criado_em',''))[:60],
                      'atualizado_em':str(x.get('atualizado_em',''))[:60]})
    for x in versoes_brutas:
        if not isinstance(x, dict) or not isinstance(x.get('html'),str):
            continue
        if len(x['html'].encode('utf8')) > MAX_HTML: continue
        html = x['html']
        versoes.append({'id':uuid4().hex, 'titulo':str(x.get('titulo',''))[:200],
                       'rotulo':str(x.get('rotulo',''))[:120],
                       'criado_em':str(x.get('criado_em',''))[:60],
                       'hash':sha256(html.encode('utf8')).hexdigest(), 'html':html})
    with LOCK:
        metadados = []
        for item in versoes:
            html = item.pop('html')
            salvar_html_versao(pasta, tipo, numero, item['id'], html)
            metadados.append(item)
        _salvar(pasta, tipo, numero, {'formato':1,'itens':itens,'versoes':metadados})
