# Walkthrough: AWS Integration Setup

I have implemented the infrastructure necessary to test and use AWS services (**TTS**, **ASR**, and **NLU**) in the AirVLC project.

## Changes Made

### 1. Project Organization
I created a new directory structure in `src/services/aws` to keep the AWS logic modular:
- `config.py`: Centralized client initialization using `boto3`.
- `polly_service.py`: Wrapper for Text-to-Speech.
- `transcribe_service.py`: Wrapper for Automatic Speech Recognition.
- `lex_service.py`: Wrapper for Natural Language Understanding.

### 2. Environment Configuration
I updated the `.env` file with a template for AWS credentials. 
> [!IMPORTANT]
> Remember to fill in `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` from your AWS Academy console.

### 3. Connectivity Test
I created `src/services/aws/test_connectivity.py`, a script that:
1.  Verifies the credentials.
2.  Lists voices in **Polly** and generates a test MP3 (`tests/test_speech.mp3`).
3.  Lists recent jobs in **Transcribe**.
4.  Lists available bots in **Lex V2**.

## How to Test

1.  Open your **AWS Academy** and copy the credentials (Access Key, Secret Key, and Session Token).
2.  Paste them into the `.env` file in the root of the project.
3.  Run the following command in your terminal:

```bash
python src/services/aws/test_connectivity.py
```

## Next Steps
- Once you verify the connectivity, we can start integrating these services into the main AirVLC pipeline (e.g., generating audio alerts from the LSTM predictions).
- If you haven't created a Lex Bot yet, we can plan the intents and slots for the air quality queries.
