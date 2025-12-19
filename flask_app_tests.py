from dataclasses import dataclass
import requests

prefix = "https://kesterallen.pythonanywhere.com"
events = [
    "fall-of-saigon",
    "opening-of-disneyland",
    "release-of-titantic",
]

routes = [
    "/",
    "/random/{}",
    "/worst/{}",
    "/worst/random",
    "/random/random",
    "/arbitrary/worst/random",
    "/arbitrary/random/random",
    "/arbitrary/worst/{}",
    "/arbitrary/random/{}",
    "/{}/{}/{}",
]

for route in routes:
    url = prefix + route.format(*events)
    response = requests.get(url)
    print(route, response)
    assert response.status_code == 200
