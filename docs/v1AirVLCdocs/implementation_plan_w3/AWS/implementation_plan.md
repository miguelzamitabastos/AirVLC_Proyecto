# AWS Integration & Connectivity Test Plan

This plan outlines the integration of AWS services (ASR, TTS, NLU) into the AirVLC project, as specified in the [implementation plan](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/docs/implementation_plan.md). We will create a robust structure in `src/services/aws` to test and eventually use these services in the mobile application.

## User Review Required

> [!IMPORTANT]
> **AWS Academy Credentials**: Since you are using a student account, your credentials (Access Key, Secret Key, and **Session Token**) are temporary. You will need to update them in the `.env` file every time you start a new session in AWS Academy.

> [!WARNING]
> **AWS Lex V2 Setup**: Unlike Polly and Transcribe, AWS Lex requires a Bot to be created in the AWS Console before it can be used via API. For the initial connectivity test, I will focus on listing available bots or verifying service access.

## Proposed Changes

### 1. Project Structure
We will organize the AWS logic within `src/services/aws` to keep it modular and reusable.

#### [NEW] [__init__.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/__init__.py)
#### [NEW] [config.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/config.py)
*   Handles loading credentials from `.env`.
*   Initializes `boto3` clients for Polly, Transcribe, and Lex.

#### [NEW] [polly_service.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/polly_service.py)
*   Wrapper for **Text-to-Speech** (TTS).
*   Function to synthesize text into an MP3 file (e.g., reading an air quality alert).

#### [NEW] [transcribe_service.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/transcribe_service.py)
*   Wrapper for **Automatic Speech Recognition** (ASR).
*   Logic to start transcription jobs for audio files.

#### [NEW] [lex_service.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/lex_service.py)
*   Wrapper for **Natural Language Understanding** (NLU).
*   Logic to send text to a Lex Bot and get the detected intent/slots.

#### [NEW] [test_connectivity.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/services/aws/test_connectivity.py)
*   A standalone script to verify that the credentials are correct and the services are reachable.

---

### 2. Environment Configuration

#### [MODIFY] [.env](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/.env)
Add the following template for AWS credentials:

```env
# --- AWS Credentials (Academy/Student) ---
AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY"
AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY"
AWS_SESSION_TOKEN="YOUR_SESSION_TOKEN"
AWS_REGION="us-east-1"
```

## Verification Plan

### Automated Tests
1.  **Polly Test**: Run `src/services/aws/test_connectivity.py`. It should generate a small `test_speech.mp3` file.
2.  **Transcribe Test**: The script will check if the service is reachable by listing transcription jobs.
3.  **Lex Test**: The script will attempt to list available bots in the region.

### Manual Verification
*   Listen to the generated `test_speech.mp3` to ensure the voice sounds correct (e.g., using a Spanish voice like "Lucia" or "Enrique").
*   Check the AWS Console to see if the API calls are being registered in the student account.

## Open Questions

1.  **Lex Bot**: Have you already created a Bot in the AWS Console? If so, please provide the `Bot ID` and `Bot Alias ID`. If not, we can create a simple one later.
2.  **Voice Preference**: For Polly, do you want a specific Spanish voice? (Standard voices: "Conchita", "Enrique", "Lucia"; Neural voices: "Lucia", "Mia").
