"""Temas das avaliações e setores do painel.

A lista é fechada: o modelo só pode marcar estes temas, e cada tema pertence a
um setor. Os temas de reclamação ficam nos setores de operação; os de elogio,
em Pontos fortes. Uma avaliação pode ter até três temas, ou nenhum, quando o
comentário não fala de nada da lista (um "ok" ou "recomendo" sem motivo).

A descrição de cada tema vai no prompt da classificação e é o critério que o
modelo segue. O rótulo é o texto que aparece no painel.
"""

from dataclasses import dataclass
from typing import Literal

Polarity = Literal["reclamacao", "elogio"]


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    sector: str
    polarity: Polarity
    description: str


@dataclass(frozen=True)
class Sector:
    id: str
    label: str
    summary: str


SECTORS = [
    Sector("logistica", "Logística", "Prazo, extravio, avaria e rastreio dos pedidos"),
    Sector("produto", "Produto e anúncio", "Defeitos, medidas e diferença entre anúncio e produto"),
    Sector(
        "vendedor", "Vendedor e atendimento", "Contato com a loja, trocas, devoluções e reembolso"
    ),
    Sector(
        "retencao", "Retenção e reputação", "O que faz o cliente voltar, recomendar ou desistir"
    ),
    Sector("fortes", "Pontos fortes", "O que os clientes mais elogiam"),
]

THEMES = [
    # Logística
    Theme(
        "atraso",
        "Atraso na entrega",
        "logistica",
        "reclamacao",
        "o pedido chegou depois do prazo prometido ou a entrega demorou demais",
    ),
    Theme(
        "nao_recebido",
        "Produto não recebido",
        "logistica",
        "reclamacao",
        "o cliente diz que ainda não recebeu o produto ou que ele nunca chegou",
    ),
    Theme(
        "incompleto",
        "Pedido incompleto",
        "logistica",
        "reclamacao",
        "chegou só parte do pedido, faltou item ou o pedido veio dividido em entregas",
    ),
    Theme(
        "avaria",
        "Chegou danificado",
        "logistica",
        "reclamacao",
        "o produto chegou quebrado, amassado, rasgado ou com a embalagem danificada",
    ),
    Theme(
        "rastreio",
        "Rastreio e falta de informação",
        "logistica",
        "reclamacao",
        "falta de informação sobre o pedido, rastreio que não atualiza ou que mostra "
        "entregue sem ter chegado",
    ),
    # Produto e anúncio
    Theme(
        "defeito",
        "Defeito",
        "produto",
        "reclamacao",
        "o produto veio com defeito, não funciona ou parou de funcionar logo",
    ),
    Theme(
        "diferente_anuncio",
        "Diferente do anúncio",
        "produto",
        "reclamacao",
        "o produto recebido é outro, de cor, modelo ou característica diferente do anúncio",
    ),
    Theme(
        "tamanho",
        "Tamanho e medidas",
        "produto",
        "reclamacao",
        "o tamanho ou as medidas não são os esperados (menor, maior, numeração errada)",
    ),
    Theme(
        "qualidade_baixa",
        "Qualidade abaixo do esperado",
        "produto",
        "reclamacao",
        "o produto funciona, mas o material ou o acabamento é ruim ou frágil",
    ),
    Theme(
        "falsificado",
        "Falsificado ou não original",
        "produto",
        "reclamacao",
        "o cliente diz que o produto é falsificado, réplica ou não é original",
    ),
    # Vendedor e atendimento
    Theme(
        "sem_resposta",
        "Loja não responde",
        "vendedor",
        "reclamacao",
        "o cliente tentou falar com a loja ou o vendedor e não teve resposta ou solução",
    ),
    Theme(
        "troca_devolucao",
        "Troca e devolução",
        "vendedor",
        "reclamacao",
        "problemas ou demora para trocar ou devolver o produto",
    ),
    Theme(
        "reembolso",
        "Estorno e reembolso",
        "vendedor",
        "reclamacao",
        "o dinheiro não foi devolvido, o estorno demorou ou a cobrança foi indevida",
    ),
    Theme(
        "cancelamento",
        "Cancelamento",
        "vendedor",
        "reclamacao",
        "o pedido foi cancelado pela loja ou o cliente teve dificuldade para cancelar",
    ),
    # Retenção e reputação
    Theme(
        "nao_volta",
        "Não volta a comprar",
        "retencao",
        "reclamacao",
        "o cliente diz que não compra mais, não recomenda ou se arrependeu da compra",
    ),
    Theme(
        "reclamacao_formal",
        "Procon ou reclamação pública",
        "retencao",
        "reclamacao",
        "o cliente cita Procon, processo, Reclame Aqui ou outra reclamação formal",
    ),
    Theme(
        "recompra",
        "Volta a comprar ou recomenda",
        "retencao",
        "elogio",
        "o cliente diz que vai comprar de novo, já é cliente ou recomenda a loja com motivo",
    ),
    # Pontos fortes
    Theme(
        "entrega_rapida",
        "Entrega rápida",
        "fortes",
        "elogio",
        "o pedido chegou rápido, no prazo ou antes do prazo",
    ),
    Theme(
        "produto_bom",
        "Produto de boa qualidade",
        "fortes",
        "elogio",
        "elogio à qualidade, ao funcionamento ou ao material do produto",
    ),
    Theme(
        "conforme_anuncio",
        "Igual ao anúncio",
        "fortes",
        "elogio",
        "o produto veio conforme a descrição, a foto ou o esperado",
    ),
    Theme(
        "bem_embalado",
        "Bem embalado",
        "fortes",
        "elogio",
        "elogio à embalagem ou ao cuidado no envio",
    ),
    Theme(
        "bom_atendimento",
        "Bom atendimento",
        "fortes",
        "elogio",
        "elogio ao vendedor ou à loja: atenção, comunicação, solução de um problema",
    ),
    Theme(
        "bom_preco",
        "Bom custo-benefício",
        "fortes",
        "elogio",
        "elogio ao preço ou à relação entre preço e qualidade",
    ),
]

THEME_IDS = frozenset(theme.id for theme in THEMES)
THEMES_BY_ID = {theme.id: theme for theme in THEMES}
SECTOR_IDS = frozenset(sector.id for sector in SECTORS)
MAX_THEMES_PER_REVIEW = 3


def themes_of_sector(sector_id: str) -> list[str]:
    return [theme.id for theme in THEMES if theme.sector == sector_id]
