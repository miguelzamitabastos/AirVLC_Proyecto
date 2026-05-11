import os
from pathlib import Path

from dotenv import load_dotenv

# Cargar `.env` desde la raíz del repo aunque el proceso arranque con otro cwd
# (p. ej. `python src/api/app.py` desde otra carpana). Sin esto, LEX_BOT_ID y
# credenciales pueden quedar vacíos y Lex falla aunque `test_connectivity` pase
# cuando se ejecuta desde la raíz del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")

class AWSConfig:
    """Handles AWS configuration and client initialization."""
    
    @staticmethod
    def get_credentials():
        """Returns a dictionary with AWS credentials from .env."""
        return {
            'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'aws_session_token': os.getenv('AWS_SESSION_TOKEN'),
            'region_name': os.getenv('AWS_REGION', 'us-east-1')
        }

    @classmethod
    def get_client(cls, service_name):
        """Initializes and returns a boto3 client for the specified service."""
        creds = cls.get_credentials()
        
        # Validate that we have at least the basic credentials
        if not creds['aws_access_key_id'] or not creds['aws_secret_access_key']:
            raise ValueError("AWS Credentials missing in .env file.")

        try:
            import boto3
        except Exception as e:
            raise RuntimeError("boto3 no está instalado; no se puede inicializar el cliente AWS.") from e

        return boto3.client(
            service_name,
            **creds
        )
