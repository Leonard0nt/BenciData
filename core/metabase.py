# You'll need to install PyJWT via pip 'pip install PyJWT' or your project packages file

import jwt
import time

METABASE_SITE_URL = "http://192.168.1.8:3000"
METABASE_SECRET_KEY = "88fe7bf75005764203c0ec080f466b0f552d8c243c243f8dddd460ef51860845"

payload = {
  "resource": {"question": 39},
  "params": {
    
  },
  "exp": round(time.time()) + (60 * 10) # 10 minute expiration
}
token = jwt.encode(payload, METABASE_SECRET_KEY, algorithm="HS256")

iframeUrl = METABASE_SITE_URL + "/embed/question/" + token + "#bordered=true&titled=true"