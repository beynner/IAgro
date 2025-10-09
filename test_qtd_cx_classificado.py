from sankhya_integration.services.oracle_conn import consultar_lotes_sumario_top11_classificaveis

# Testar com o lote 251009P536P27S01
controle = '251009P536P27S01'

print("=" * 80)
print(f"TESTE: Quantidade de Caixas - Lote {controle}")
print("=" * 80)

resultado = consultar_lotes_sumario_top11_classificaveis([controle])

if controle in resultado:
    info = resultado[controle]
    print(f"\n📦 Parceiro: {info.get('parceiro', 'N/A')}")
    print(f"📦 CODPARC: {info.get('codparc', 'N/A')}")
    print(f"\n📊 QUANTIDADES:")
    print(f"   • Qtd CX (entrada TOP 11): {info.get('qtd_cx', 0):.2f} caixas")
    print(f"   • Qtd KG (entrada TOP 11): {info.get('qtd_kg', 0):.2f} kg")
    print(f"   • Peso In Natura: {info.get('peso_inn', 0):.2f} kg/cx")
    print(f"   ✅ Qtd CX CLASSIFICADO (TOP 26): {info.get('qtd_cx_classificado', 0):.2f} caixas")
    
    print(f"\n📋 STATUS CLASSIFICAÇÃO:")
    print(f"   • NUNOTA Classificação: {info.get('nunota_class', 'N/A')}")
    print(f"   • Status Nota: {info.get('statusnota_class', 'N/A')}")
    
    print(f"\n🏭 PRODUTOS DE ENTRADA:")
    produtos = info.get('produtos_entrada', [])
    if produtos:
        for p in produtos:
            print(f"   • Produto {p.get('cod')}: {p.get('fabricante', 'N/A')}")
    else:
        print("   (Nenhum produto encontrado)")
    
    # Verificar qual valor será exibido
    qtd_classif = info.get('qtd_cx_classificado', 0)
    qtd_entrada = info.get('qtd_cx', 0)
    
    print(f"\n💡 LÓGICA DE EXIBIÇÃO:")
    if qtd_classif > 0:
        print(f"   ✅ Exibir: {qtd_classif:.2f} caixas (CLASSIFICADO - soma Extra+Médio+etc)")
    else:
        print(f"   ⚠️  Exibir: {qtd_entrada:.2f} caixas (ENTRADA - ainda não classificado)")
        
else:
    print(f"\n❌ Lote {controle} não encontrado!")

print("\n" + "=" * 80)
