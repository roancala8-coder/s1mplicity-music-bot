from yt_dlp.extractor.common import InfoExtractor

class AudiomackIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?audiomack\.com/(?:[^/]+)/(?:song|album)/(?P<id>[^/?#&]+)'
    
    def _real_extract(self, url):
        song_id = self._match_id(url)
        
        api_url = f'https://audiomack.com/api/music/slug/{song_id}'
        
        json_data = self._download_json(api_url, song_id)
        
        audio_url = json_data.get('url')
        
        return {
            'id': song_id,
            'title': json_data.get('title'),
            'artist': json_data.get('artist'),
            'url': audio_url,
            'ext': 'mp3',
        }