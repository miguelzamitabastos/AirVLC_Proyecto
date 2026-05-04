"""
Script rápido para obtener los IDs de tus bots de Lex.
Ejecución: python -m src.services.aws.get_lex_ids
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.services.aws.lex_service import LexService

lex = LexService()
print("🤖 Bots disponibles en tu cuenta:\n")

bots = lex.list_bots()
for bot in bots:
    bot_id = bot.get('botId', 'N/A')
    bot_name = bot.get('botName', 'N/A')
    status = bot.get('botStatus', 'N/A')
    print(f"  📌 Bot: {bot_name}")
    print(f"     Bot ID:  {bot_id}")
    print(f"     Status:  {status}")

    # Intentar obtener los alias del bot
    try:
        aliases_response = lex.model_client.list_bot_aliases(botId=bot_id, maxResults=10)
        aliases = aliases_response.get('botAliasSummaries', [])
        for alias in aliases:
            alias_id = alias.get('botAliasId', 'N/A')
            alias_name = alias.get('botAliasName', 'N/A')
            alias_status = alias.get('botAliasStatus', 'N/A')
            print(f"     Alias:   {alias_name} → Alias ID: {alias_id} (status: {alias_status})")
    except Exception as e:
        print(f"     ⚠️ No se pudieron listar los alias: {e}")

    print()

print("─" * 50)
print("📋 Copia el Bot ID y el Bot Alias ID de 'AirVLCBot' y añádelos a tu .env:")
print("   LEX_BOT_ID=\"<tu_bot_id>\"")
print("   LEX_BOT_ALIAS_ID=\"<tu_alias_id>\"")
