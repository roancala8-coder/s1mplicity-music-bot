import re
import json
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError

class AudiomackIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?audiomack\.com/(?P<artist>[^/]+)/(?:song|album|playlist)/(?P<id>[^/?#&]+)'

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        artist = mobj.group('artist')
        song_id = mobj.group('id')
        display_id = f'{artist}/{song_id}'

        # Download the webpage
        webpage = self._download_webpage(url, display_id)

        # Method 1: Try to find the audio URL directly in the page source
        # Look for standard HTML5 audio source
        audio_url = self._search_regex(
            r'<source[^>]+src="([^"]+)"[^>]*>', webpage, 'audio url', default=None
        )
        
        # Method 2: If not found, look for the JSON-LD structured data
        if not audio_url:
            json_ld_data = self._search_regex(
                r'<script type="application/ld\+json">(.*?)</script>', 
                webpage, 'json-ld', default=None, flags=re.DOTALL
            )
            if json_ld_data:
                try:
                    data = json.loads(json_ld_data)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'MusicRecording' and item.get('contentUrl'):
                                audio_url = item.get('contentUrl')
                                break
                except:
                    pass

        # Method 3: Try a different regex for the audio source
        if not audio_url:
            audio_url = self._search_regex(
                r'data-audio-url="([^"]+)"', webpage, 'audio url (data attr)', default=None
            )

        # Method 4: Try to find a direct download link
        if not audio_url:
            audio_url = self._search_regex(
                r'(https?:\/\/[^"\']+\.mp3[^"\']*)', webpage, 'mp3 url', default=None
            )

        if not audio_url:
            raise ExtractorError('Could not extract audio URL from Audiomack page. The site structure may have changed.')

        # Extract title from the page
        title = self._og_search_title(webpage, default=song_id)
        # Clean up title (remove "by Artist" suffix if present)
        title = re.sub(r'\s+by\s+.*$', '', title)

        return {
            'id': song_id,
            'title': title,
            'artist': artist,
            'url': audio_url,
            'ext': 'mp3',
        }