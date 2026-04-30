from .config import AWSConfig

class LexService:
    """Service for Natural Language Understanding (NLU) using AWS Lex V2."""
    
    def __init__(self):
        # We use lexv2-runtime for interacting with the bot
        self.runtime_client = AWSConfig.get_client('lexv2-runtime')
        self.model_client = AWSConfig.get_client('lexv2-models')

    def recognize_text(self, bot_id, bot_alias_id, locale_id, text, session_id='test-session'):
        """Sends text to a Lex bot and returns the recognized intent."""
        try:
            response = self.runtime_client.recognize_text(
                botId=bot_id,
                botAliasId=bot_alias_id,
                localeId=locale_id,
                sessionId=session_id,
                text=text
            )
            return response
        except Exception as e:
            print(f"Error in Lex recognize_text: {e}")
            raise e

    def list_bots(self):
        """Lists available bots to verify connectivity."""
        try:
            response = self.model_client.list_bots(maxResults=5)
            return response.get('botSummaries', [])
        except Exception as e:
            print(f"Error listing Lex bots: {e}")
            return []
            
    def test_connection(self):
        """Simple connectivity check for Lex service."""
        try:
            # Just try to list bots as a permission check
            bots = self.list_bots()
            return True, f"Found {len(bots)} bots."
        except Exception as e:
            return False, str(e)
