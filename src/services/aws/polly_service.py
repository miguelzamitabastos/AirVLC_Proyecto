import os
from .config import AWSConfig

class PollyService:
    """Service for Text-to-Speech (TTS) using AWS Polly."""
    
    def __init__(self):
        self.client = AWSConfig.get_client('polly')

    def synthesize_speech(self, text, output_file, voice_id='Lucia', engine='neural'):
        """
        Converts text to an MP3 file.
        Default voice 'Lucia' (Spanish, Female, Neural).
        """
        try:
            print(f"Synthesizing speech for: '{text[:50]}...'")
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine
            )
            
            if "AudioStream" in response:
                with open(output_file, 'wb') as f:
                    f.write(response['AudioStream'].read())
                print(f"Successfully saved audio to {output_file}")
                return output_file
            
        except Exception as e:
            print(f"Error in Polly synthesize_speech: {e}")
            raise e

    def list_voices(self, language_code='es-ES'):
        """Lists available voices for a specific language."""
        try:
            response = self.client.describe_voices(LanguageCode=language_code)
            return response.get('Voices', [])
        except Exception as e:
            print(f"Error listing voices: {e}")
            return []
