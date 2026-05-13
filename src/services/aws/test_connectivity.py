import os
import sys
from pathlib import Path

# Add the project root to sys.path to allow imports from src
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.services.aws.polly_service import PollyService
from src.services.aws.transcribe_service import TranscribeService
from src.services.aws.lex_service import LexService

def test_aws_connectivity():
    print("=== AWS Connectivity Test for AirVLC ===\n")
    
    # Check if credentials are set
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    if not access_key:
        print("❌ ERROR: AWS_ACCESS_KEY_ID not found in .env")
        print("Please fill in your credentials in the .env file first.")
        return

    # 1. Test Polly
    print("1. Testing AWS Polly (TTS)...")
    try:
        polly = PollyService()
        voices = polly.list_voices()
        if voices:
            print(f"✅ Success: Found {len(voices)} voices for es-ES.")
            # Optional: Generate a small test file
            output_path = "tests/test_speech.mp3"
            os.makedirs("tests", exist_ok=True)
            polly.synthesize_speech("Hola Miguel, la calidad del aire en Valencia es buena hoy.", output_path)
            print(f"✅ Success: Generated test audio at {output_path}")
        else:
            print("⚠️ Warning: Connected to Polly but no voices found for es-ES.")
    except Exception as e:
        print(f"❌ Polly Error: {e}")

    print("\n" + "-"*30 + "\n")

    # 2. Test Transcribe
    print("2. Testing AWS Transcribe (ASR)...")
    try:
        transcribe = TranscribeService()
        jobs = transcribe.list_jobs()
        print(f"✅ Success: Connected to Transcribe. Found {len(jobs)} recent jobs.")
    except Exception as e:
        print(f"❌ Transcribe Error: {e}")

    print("\n" + "-"*30 + "\n")

    # 3. Test Lex
    print("3. Testing AWS Lex V2 (NLU)...")
    try:
        lex = LexService()
        bots = lex.list_bots()
        print(f"✅ Success: Connected to Lex V2. Found {len(bots)} bots.")
    except Exception as e:
        print(f"❌ Lex Error: {e}")

    print("\n" + "="*40)
    print("Test finished. If you see 'Success' in all sections, your AWS credentials are valid!")

if __name__ == "__main__":
    test_aws_connectivity()
