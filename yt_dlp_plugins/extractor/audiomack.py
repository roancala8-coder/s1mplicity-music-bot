import re
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError

class AudiomackIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?audiomack\.com/(?P<artist>[^/]+)/(?:song|album|playlist)/(?P<id>[^/?#&]+)'
    _TESTS = [{
        'url': 'https://audiomack.com/illgiveyoustars/song/i-challenge-the-apache',
        'info_dict': {
            'id': 'i-challenge-the-apache',
            'ext': 'mp3',
            'title': 'I Challenge The Apache',
            'artist': 'illgiveyoustars',
        },
    }]

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        artist = mobj.group('artist')
        song_id = mobj.group('id')
        display_id = f'{artist}/{song_id}'

        # Use the correct v1 API endpoint for song details
        api_url = f'https://api.audiomack.com/v1/music/song/{artist}/{song_id}'
        
        json_data = self._download_json(api_url, display_id, expected_status=200)
        
        if not json_data:
            raise ExtractorError('Failed to retrieve track data from Audiomack API')
        
        # Extract the streaming URL
        audio_url = json_data.get('url')
        if not audio_url:
            # Fallback: try to get it via the 'play' endpoint
            play_url = f'https://api.audiomack.com/v1/music/{json_data.get("id")}/play'
            play_data = self._download_json(play_url, display_id, fatal=False)
            audio_url = play_data.get('url') if play_data else None
        
        if not audio_url:
            raise ExtractorError('Could not extract audio URL from API response')
        
        return {
            'id': song_id,
            'title': json_data.get('title'),
            'artist': json_data.get('artist') or artist,
            'url': audio_url,
            'ext': 'mp3',
            'thumbnail': json_data.get('cover_art'),
        }