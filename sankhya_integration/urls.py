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

    # 📊 DASHBOARD EXECUTIVO (Mai/2026)
    path("api/dashboard/", views.api_dashboard_indicadores, name="api_dashboard_indicadores"),

    # 📋 AUDITORIA UNIVERSAL (Mai/2026 — Lote A)
    path("auditoria/",              views.view_auditoria_painel,  name="view_auditoria_painel"),

    # 📊 RELATÓRIOS (Mai/2026 — 2026-05-17) — MVP com 5 relatórios em sub-abas
    path("relatorios/",                       views.view_relatorios_painel,            name="view_relatorios_painel"),
    path("relatorios/api/top-clientes-produtos/", views.api_relatorio_top_clientes_produtos, name="api_relatorio_top_clientes_produtos"),
    path("relatorios/api/lotes-envelhecidos/",    views.api_relatorio_lotes_envelhecidos,    name="api_relatorio_lotes_envelhecidos"),
    path("relatorios/api/consumo-veiculos/",      views.api_relatorio_consumo_veiculos,      name="api_relatorio_consumo_veiculos"),
    path("relatorios/api/fluxo-caixa/",           views.api_relatorio_fluxo_caixa,           name="api_relatorio_fluxo_caixa"),
    path("relatorios/api/margem-venda/",          views.api_relatorio_margem_venda,          name="api_relatorio_margem_venda"),
    path("api/auditoria/listar/",   views.api_auditoria_listar,   name="api_auditoria_listar"),
    path("api/auditoria/filtros/",  views.api_auditoria_filtros,  name="api_auditoria_filtros"),
    
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
    # Vendas DO LOTE selecionado (Mai/2026) — filtra por CODAGREGACAO + dedup
    # pedido↔nota. Alimenta lista lateral + sparkline de evolução de preço.
    path('comercial/api/vendas-lote/',          views.api_vendas_do_lote,       name='api_vendas_do_lote'),
    # Margem realizada/provisória do lote (Mai/2026 — 2026-05-17): preenche
    # card "Margem Lote" no Distribuição. Receita − Devolução − Custo, com
    # avaria informativa no tooltip.
    path('comercial/api/margem-lote/',          views.api_margem_lote,          name='api_margem_lote'),

    # A rota do Ticket Médio
    path('comercial/api/ticket-calculo/', views.api_ticket_calculo, name='api_ticket_calculo'),


# ==============================================================================
# 💰 MÓDULO DE VENDA (PEDIDOS TOP 34 / VENDAS TOP 35/37)
# ==============================================================================
    path("venda/portal/", views.view_portal_vendas, name="venda_portal"),
    path("venda/api/listar/", views.api_listar_vendas, name="api_listar_vendas"),
    path("venda/api/cabecalho/", views.api_criar_cabecalho_venda, name="api_criar_cabecalho_venda"),
    path("venda/api/item/", views.api_salvar_item_venda, name="api_salvar_item_venda"),
    path("venda/api/item/editar/", views.api_atualizar_item_venda, name="api_atualizar_item_venda"),
    path("venda/api/item/remover/", views.api_remover_item_venda, name="api_remover_item_venda"),
    path("venda/api/excluir/", views.api_excluir_pedido_venda, name="api_excluir_pedido_venda"),
    path("venda/api/cabecalho/obter/", views.api_obter_cabecalho_pedido, name="api_obter_cabecalho_pedido"),
    path("venda/api/cabecalho/editar/", views.api_atualizar_cabecalho_venda, name="api_atualizar_cabecalho_venda"),
    path("venda/api/faturar/", views.api_faturar_pedido_venda, name="api_faturar_pedido_venda"),

    # Mai/2026 — Avaria (TOP 30) + Devolução (TOP 36) + Histórico de Lote
    path("venda/api/avaria/criar/",          views.api_criar_avaria,              name="api_criar_avaria"),
    path("venda/api/devolucao/preparar/",    views.api_obter_nota_para_devolucao, name="api_obter_nota_para_devolucao"),
    path("venda/api/devolucao/criar/",       views.api_criar_devolucao,           name="api_criar_devolucao"),
    path("venda/api/lote/historico/",        views.api_historico_lote,            name="api_historico_lote"),

# ==============================================================================
# 💰 MÓDULO DE RASTREABILIDADE
# ==============================================================================

    path('rastreio/', views.api_rastreio_view, name='rastreio'),
    path('rastreio/api/fabricantes/',       views.api_rastreio_fabricantes,        name='api_rastreio_fabricantes'),
    path('rastreio/api/lote-vinculos/',     views.api_rastreio_lote_vinculos,      name='api_rastreio_lote_vinculos'),
    path('rastreio/api/lotes-disponiveis/', views.api_rastreio_lotes_disponiveis, name='api_rastreio_lotes_disponiveis'),
    path('rastreio/api/pedidos-abertos/',   views.api_rastreio_pedidos_abertos,   name='api_rastreio_pedidos_abertos'),
    # atribuir/desvincular aceitam TOP 34 STATUSNOTA='L' (Mai/2026 — rastreabilidade
    # vive no pedido mesmo após faturamento; nota TOP 35/37 não é tocada)
    path('rastreio/api/atribuir-lote/',           views.api_rastreio_atribuir_lote,           name='api_rastreio_atribuir_lote'),
    path('rastreio/api/desvincular-lote/',        views.api_rastreio_desvincular_lote,        name='api_rastreio_desvincular_lote'),
    # Vínculo manual pedido↔nota (Leva A Mai/2026): quando TGFVAR não foi populado
    path('rastreio/api/vinculo/candidatos/',          views.api_rastreio_vinculo_candidatos,           name='api_rastreio_vinculo_candidatos'),
    path('rastreio/api/vinculo/criar/',               views.api_rastreio_vinculo_criar,                name='api_rastreio_vinculo_criar'),
    path('rastreio/api/vinculo/remover/',             views.api_rastreio_vinculo_remover,              name='api_rastreio_vinculo_remover'),
    # Pedido retroativo (Leva B Mai/2026): nota direta sem pedido — IAgro cria
    path('rastreio/api/vinculo/criar-pedido-retroativo/', views.api_rastreio_vinculo_criar_pedido_retroativo, name='api_rastreio_vinculo_criar_pedido_retroativo'),
    # Fluxo unificado A+B (Mai/2026): backend decide vincular ou criar
    path('rastreio/api/vinculo/resolver/',                views.api_rastreio_vinculo_resolver,                 name='api_rastreio_vinculo_resolver'),
    # Etiquetas SafeTrace/IAgro (Mai/2026): PDF 100×50mm pra impressora Zebra ZD220
    path('rastreio/api/etiqueta-pdf/',                    views.api_rastreio_etiqueta_pdf,                     name='api_rastreio_etiqueta_pdf'),
    # Resolução de peso (TOP 26) — frontend chama antes do PDF pra detectar
    # linhas com múltiplos pesos e abrir modal de escolha (Mai/2026)
    path('rastreio/api/resolver-peso/',                   views.api_rastreio_resolver_peso,                    name='api_rastreio_resolver_peso'),
    # Refresh manual do AD_SALDO_LOTE_CACHE — disparado pelo botão Atualizar
    # quando operador precisa de dado fresco antes do próximo ciclo do cron 5min
    path('rastreio/api/refresh-saldo/',                   views.api_rastreio_refresh_saldo,                    name='api_rastreio_refresh_saldo'),

# ==============================================================================
# 📧 MÓDULO IMPORTAÇÃO POR E-MAIL (PEDIDOS COM PDF + LLM LOCAL)
# ==============================================================================
    path('venda/email-importar/',                       views.view_email_importar,        name='email_importar'),
    path('venda/api/email/listar/',                     views.api_email_listar,           name='api_email_listar'),
    path('venda/api/email/importar-texto/',             views.api_email_importar_texto,   name='api_email_importar_texto'),
    path('venda/api/email/<int:recebido_id>/',          views.api_email_obter,            name='api_email_obter'),
    path('venda/api/email/<int:recebido_id>/pdf/',      views.api_email_pdf,              name='api_email_pdf'),
    path('venda/api/email/<int:recebido_id>/descartar/',views.api_email_descartar,        name='api_email_descartar'),
    path('venda/api/email/<int:recebido_id>/reparser/', views.api_email_reparser,         name='api_email_reparser'),
    path('venda/api/email/<int:recebido_id>/confirmar/',views.api_email_confirmar,        name='api_email_confirmar'),
    path('venda/api/email/item/<int:item_id>/editar/',  views.api_email_atualizar_item,   name='api_email_atualizar_item'),
    path('venda/api/email/item/<int:item_id>/remover/', views.api_email_remover_item,     name='api_email_remover_item'),
    path('venda/api/email/<int:recebido_id>/item/criar/', views.api_email_criar_item,     name='api_email_criar_item'),
    # Restauração sem rodar LLM (re-cria itens a partir do JSON crú salvo)
    path('venda/api/email/<int:recebido_id>/restaurar/',     views.api_email_restaurar_todos, name='api_email_restaurar_todos'),
    path('venda/api/email/item/<int:item_id>/restaurar/',    views.api_email_restaurar_item,  name='api_email_restaurar_item'),

# ==============================================================================
# ⛽ MÓDULO CONTROLE DE COMBUSTÍVEL (TOP 10 entrada Sankhya + TOP 26 requisição IAgro)
# ==============================================================================
    path('combustivel/',                              views.view_portal_combustivel,           name='combustivel_portal'),
    path('combustivel/api/estoque/',                  views.api_listar_estoque_combustivel,    name='api_combustivel_estoque'),
    path('combustivel/api/veiculos/',                 views.api_listar_veiculos,               name='api_combustivel_veiculos'),
    path('combustivel/api/produtos/',                 views.api_listar_produtos_combustivel,   name='api_combustivel_produtos'),
    path('combustivel/api/movimentacoes/',            views.api_listar_movimentacoes_combustivel, name='api_combustivel_movimentacoes'),
    path('combustivel/api/requisicoes/',              views.api_listar_requisicoes_combustivel, name='api_combustivel_requisicoes'),
    path('combustivel/api/requisicao/<int:nunota>/',         views.api_obter_requisicao_combustivel,   name='api_combustivel_obter_requisicao'),
    path('combustivel/api/requisicao/criar/',                views.api_criar_requisicao_combustivel,   name='api_combustivel_criar_requisicao'),
    path('combustivel/api/abastecimento-externo/criar/',     views.api_criar_abastecimento_externo,    name='api_combustivel_criar_externo'),
    path('combustivel/api/requisicao/<int:nunota>/editar/',  views.api_editar_requisicao_combustivel,  name='api_combustivel_editar_requisicao'),
    path('combustivel/api/requisicao/<int:nunota>/excluir/', views.api_excluir_requisicao_combustivel, name='api_combustivel_excluir_requisicao'),
    path('combustivel/api/entrada/criar/',                   views.api_criar_entrada_combustivel,      name='api_combustivel_criar_entrada'),
    path('combustivel/api/entrada/<int:nunota>/',            views.api_obter_entrada_combustivel,      name='api_combustivel_obter_entrada'),
    path('combustivel/api/entrada/<int:nunota>/editar/',     views.api_editar_entrada_combustivel,     name='api_combustivel_editar_entrada'),
    path('combustivel/api/entrada/<int:nunota>/excluir/',    views.api_excluir_entrada_combustivel,    name='api_combustivel_excluir_entrada'),
    path('combustivel/api/prazo-tipvenda/',                  views.api_prazo_tipvenda,                 name='api_combustivel_prazo_tipvenda'),
    path('combustivel/api/ultimo-preco/',                    views.api_ultimo_preco_combustivel,       name='api_combustivel_ultimo_preco'),
    path('combustivel/api/veiculo-foto/<str:placa>/',        views.api_foto_veiculo,                   name='api_combustivel_veiculo_foto'),
    path('combustivel/api/relatorio/consumo/',               views.api_relatorio_consumo_veiculo,      name='api_combustivel_relatorio_consumo'),

    # ==============================================================================
    # ⚙️ HUB DE CONFIGURAÇÕES (Mai/2026)
    # Acessado pela engrenagem no header. Sidebar fica só com módulos
    # operacionais. Acesso restrito: grupos 1 (Diretoria) + 6 (Suporte).
    # ==============================================================================
    path('configuracoes/',                             views.view_configuracoes_painel,   name='view_configuracoes_painel'),

    # ==============================================================================
    # 👥 MÓDULO USUÁRIOS (Mai/2026) — gestão de acesso TSIUSU/TSIGPU
    # Cat A entregue (leituras + página). Escritas Cat B em stubs 501.
    # ==============================================================================
    path('usuarios/',                                  views.view_usuarios_painel,        name='view_usuarios_painel'),
    path('usuarios/api/listar/',                       views.api_usuarios_listar,         name='api_usuarios_listar'),
    path('usuarios/api/grupos/',                       views.api_usuarios_grupos,         name='api_usuarios_grupos'),
    path('usuarios/api/<int:codusu>/',                 views.api_usuarios_detalhe,        name='api_usuarios_detalhe'),
    # Cat B (stubs 501 até aprovação ponto-a-ponto)
    path('usuarios/api/criar/',                        views.api_usuarios_criar,          name='api_usuarios_criar'),
    path('usuarios/api/<int:codusu>/editar/',          views.api_usuarios_atualizar,      name='api_usuarios_atualizar'),
    path('usuarios/api/<int:codusu>/inativar/',        views.api_usuarios_inativar,       name='api_usuarios_inativar'),
    path('usuarios/api/<int:codusu>/reativar/',        views.api_usuarios_reativar,       name='api_usuarios_reativar'),
    path('usuarios/api/<int:codusu>/grupo/adicionar/', views.api_usuarios_adicionar_grupo, name='api_usuarios_adicionar_grupo'),
    path('usuarios/api/<int:codusu>/grupo/remover/',   views.api_usuarios_remover_grupo,   name='api_usuarios_remover_grupo'),

    # ==============================================================================
    # 📦 MÓDULO CAIXAS (Mai/2026) — Controle de vasilhame retornável
    # Cat A entregue (saldo + timeline + listagens). Escritas Cat B em stubs 501.
    # ==============================================================================
    path('caixas/',                                    views.view_caixas_painel,           name='view_caixas_painel'),
    path('caixas/api/saldo/',                          views.api_caixas_saldo,             name='api_caixas_saldo'),
    path('caixas/api/timeline/<int:codparc>/',         views.api_caixas_timeline,          name='api_caixas_timeline'),
    path('caixas/api/coletas/',                        views.api_caixas_coletas_listar,    name='api_caixas_coletas_listar'),
    path('caixas/api/produtos/',                       views.api_caixas_produtos_listar,   name='api_caixas_produtos_listar'),
    # Cat B (stubs 501 até aprovação ponto-a-ponto)
    path('caixas/api/coleta/criar/',                   views.api_caixas_coleta_criar,      name='api_caixas_coleta_criar'),
    path('caixas/api/coleta/<int:id_coleta>/estornar/',views.api_caixas_coleta_estornar,   name='api_caixas_coleta_estornar'),
    path('caixas/api/produto/upsert/',                 views.api_caixas_produto_upsert,    name='api_caixas_produto_upsert'),
    # [TEMPORÁRIO Mai/2026] Backfill PESO via moda TOP 26 — REMOVER quando IAgro virar fluxo único
    path('caixas/api/refresh-pesos/',                  views.api_caixas_refresh_pesos,     name='api_caixas_refresh_pesos'),
]