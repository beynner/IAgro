from django.urls import path
from . import views

urlpatterns = [

    # ==============================================================================
    # 🔒 AUTENTICAÇÃO
    # ==============================================================================
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    
    # ==============================================================================
    # 🌍 INFRAESTRUTURA GERAL
    # ==============================================================================
    #path("", views.home, name="sankhya_home"),
    path("health/", views.health, name="sankhya_health"),
    
    # TYPEAHEADS (Buscas Globais)
    path("parceiros/search/", views.api_pesquisar_parceiros, name="parceiros_search"),
    path("top/search/", views.api_pesquisar_tipos_operacao, name="top_search"),
    path("natureza/search/", views.api_pesquisar_naturezas, name="natureza_search"),
    path("tipvenda/search/", views.api_pesquisar_tipos_negociacao, name="tipvenda_search"),
    path("empresa/search/", views.api_pesquisar_empresas, name="empresa_search"),
    path("cencus/search/", views.api_pesquisar_centros_resultado, name="cencus_search"),
    path('produtos/search/', views.api_pesquisar_produtos_entrada, name='api_pesquisar_produtos_entrada'),
    path('produtos/search/fabricante/', views.api_pesquisar_produtos_fabricante, name='api_pesquisar_produtos_fabricante'),
    path("vol/search/", views.api_pesquisar_volumes, name="vol_search"),
    path("lote/search/", views.api_pesquisar_lotes, name="lote_search"),

    path('pedidos/search/', views.api_pesquisar_pedidos, name='api_pesquisar_pedidos'),
    path('lotes/search/', views.api_pesquisar_lotes, name='api_pesquisar_lotes'),

    # ==============================================================================
    # 📦 MÓDULO DE ENTRADA (COMPRAS / TOP 11)
    # ==============================================================================
    
    # TELAS (Renders)
    path("compras/portal/", views.view_portal_entradas, name="compras_portal"),

    path("compras/central/", views.view_central_compras, name="compras_central"),

    # CABEÇALHO (Operações na TGFCAB)
    path("compras/central/salvar/", views.api_salvar_novo_cabecalho, name="compras_central_salvar"),
    path("header/update/", views.api_atualizar_cabecalho_existente, name="header_update"),
    path("nota/delete/", views.api_excluir_nota_compra, name="nota_delete"),
    path("item/finalize/", views.api_finalizar_nota_compra, name="item_finalize"),
    
    # ITENS DA NOTA (Operações na TGFITE)
    path("item/list/", views.api_listar_itens_nota, name="item_list"),
    path("item/save/", views.api_salvar_item_nota, name="item_save"),
    path("item/delete/", views.api_excluir_itens_nota, name="item_delete"),

    # ==============================================================================
    # 🧪 MÓDULO CLASSIFICAÇÃO (ITENS IN NATURA -> PRODUTOS ACABADOS / TOP 26)
    # ==============================================================================
    
    # Note o acréscimo de 'compras/' no início do path
    path("compras/classificacao/", views.view_classificacao_lotes, name="classificacao_lote"),
    path("compras/classificacao/api/lotes/", views.api_listar_lotes_classificacao, name="api_lotes_classificacao"),
    path("compras/classificacao/api/detalhes/", views.api_detalhes_lote_classificacao, name="api_detalhes_lote"),

    # Rota para alimentar os modais de classificação (Duplo Clique)
    path('lote/consultar/', views.api_consultar_lote, name='api_consultar_lote'),
    
    path('produtos/search/modal/', views.api_pesquisar_produtos_modal, name='api_pesquisar_produtos_modal'),
    
    # ⭐ ROTA PARA SALVAR O DESCARTE
    path('item/update_descarte_lote/', views.api_update_descarte_lote, name='api_update_descarte_lote'),

    path('item/toggle_status/', views.api_finaliza_classificacao_toggle, name='api_finaliza_classificacao_toggle'),



    # ==============================================================================
    # 💰 MÓDULO COMERCIAL
    # ==============================================================================
    
    path("comercial/", views.view_comercial_painel, name="comercial_painel"),
    path("comercial/lista/", views.api_listar_vales_comercial, name="api_listar_vales_comercial"),
    path("comercial/api/atualizar-preco/", views.api_atualizar_preco_comercial, name="api_atualizar_preco_comercial"),
    path("comercial/api/atualizar-peso/", views.api_atualizar_peso_comercial, name="api_atualizar_peso_comercial"),
    path('comercial/api/salvar-vale/', views.api_salvar_vale_comercial, name='api_salvar_vale_comercial'),
    path('comercial/api/zerar-negociacao/', views.api_zerar_negociacao, name='api_zerar_negociacao'),
    path('comercial/api/detalhes-vale/', views.api_detalhes_vale_comercial, name='api_detalhes_vale_comercial'),
    path('comercial/api/salvar-simulacao/', views.api_salvar_simulacao, name='api_salvar_simulacao'),
    path('comercial/api/efetivar-faturamento/', views.api_gerar_financeiro_banco, name='api_gerar_financeiro_banco'),
    path('comercial/api/atualizar-preco-modalFaturamento/', views.api_atualizar_preco_modalFaturamento, name='api_atualizar_preco_modalFaturamento'),
    path('comercial/api/atualizar-desconto-inss/', views.api_atualizar_desconto_inss_vale, name='api_atualizar_desconto_inss_vale'),
    path('comercial/api/desfaturar-vale/', views.api_desfaturar_vale, name='api_desfaturar_vale'),

    path('comercial/api/desmembrar-pedido-classificacao/', views.api_desmembrar_pedido_classificacao, name='api_desmembrar_pedido_classificacao'),
    path('comercial/api/listar-pedidos-unificacao/', views.api_listar_pedidos_unificacao, name='api_listar_pedidos_unificacao'),
    path('comercial/api/unificar-pedido-classificacao/', views.api_unificar_pedido_classificacao, name='api_unificar_pedido_classificacao'),

# A rota da Lista
    path('comercial/api/lista-ultimas-vendas/', views.api_lista_ultimas_vendas, name='api_lista_ultimas_vendas'),
    
    # A rota do Ticket Médio 
    path('comercial/api/ticket-calculo/', views.api_ticket_calculo, name='api_ticket_calculo'),


# ==============================================================================
# 💰 MÓDULO DE VENDA (PEDIDOS TOP 34 / VENDAS TOP 35/37)
# ==============================================================================
    path("venda/portal/", views.view_portal_vendas, name="venda_portal"),
    path("venda/api/listar/", views.api_listar_vendas, name="api_listar_vendas"),
    path("venda/api/cabecalho/", views.api_criar_cabecalho_venda, name="api_criar_cabecalho_venda"),
    path("venda/api/item/", views.api_salvar_item_venda, name="api_salvar_item_venda"),
    path("venda/api/excluir/", views.api_excluir_pedido_venda, name="api_excluir_pedido_venda"),
    path("venda/api/cabecalho/obter/", views.api_obter_cabecalho_pedido, name="api_obter_cabecalho_pedido"),
    path("venda/api/cabecalho/editar/", views.api_atualizar_cabecalho_venda, name="api_atualizar_cabecalho_venda"),

# ==============================================================================
# 💰 MÓDULO DE RASTREABILIDADE
# ==============================================================================

    path('rastreio/', views.api_rastreio_view, name='rastreio'),
    path('rastreio/api/fabricantes/',       views.api_rastreio_fabricantes,        name='api_rastreio_fabricantes'),
    path('rastreio/api/lote-vinculos/',     views.api_rastreio_lote_vinculos,      name='api_rastreio_lote_vinculos'),
    path('rastreio/api/lotes-disponiveis/', views.api_rastreio_lotes_disponiveis, name='api_rastreio_lotes_disponiveis'),
    path('rastreio/api/pedidos-abertos/',   views.api_rastreio_pedidos_abertos,   name='api_rastreio_pedidos_abertos'),
    path('rastreio/api/atribuir-lote/',     views.api_rastreio_atribuir_lote,     name='api_rastreio_atribuir_lote'),
    path('rastreio/api/desvincular-lote/',  views.api_rastreio_desvincular_lote,  name='api_rastreio_desvincular_lote'),
]