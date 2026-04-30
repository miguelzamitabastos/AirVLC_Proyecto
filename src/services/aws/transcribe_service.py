import time
from .config import AWSConfig

class TranscribeService:
    """Service for Automatic Speech Recognition (ASR) using AWS Transcribe."""
    
    def __init__(self):
        self.client = AWSConfig.get_client('transcribe')

    def start_transcription_job(self, job_name, media_uri, language_code='es-ES'):
        """Starts a transcription job for an audio file in S3."""
        try:
            print(f"Starting transcription job: {job_name}")
            response = self.client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': media_uri},
                MediaFormat='mp3',
                LanguageCode=language_code
            )
            return response
        except Exception as e:
            print(f"Error starting transcription job: {e}")
            raise e

    def get_transcription_status(self, job_name):
        """Checks the status of a transcription job."""
        try:
            response = self.client.get_transcription_job(TranscriptionJobName=job_name)
            return response['TranscriptionJob']
        except Exception as e:
            print(f"Error getting transcription status: {e}")
            raise e

    def list_jobs(self):
        """Lists recent transcription jobs to verify connectivity."""
        try:
            response = self.client.list_transcription_jobs(MaxResults=5)
            return response.get('TranscriptionJobSummaries', [])
        except Exception as e:
            print(f"Error listing transcription jobs: {e}")
            return []
