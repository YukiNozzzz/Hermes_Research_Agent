"""Bounded HTTPS-only arXiv Atom client. No model calls, credentials or arbitrary URLs."""

from datetime import datetime,timezone
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from ..models import ResearchError,require

ATOM={"a":"http://www.w3.org/2005/Atom"}


def parse_feed(data):
    require(len(data)<=5_000_000 and b"<!DOCTYPE" not in data.upper(),"INVALID_FEED","Feed is too large or contains a DTD.")
    try:
        root=ET.fromstring(data)
    except ET.ParseError as exc:
        raise ResearchError("INVALID_FEED","arXiv returned malformed XML; this is not an empty paper update.") from exc
    require(root.tag=="{http://www.w3.org/2005/Atom}feed","INVALID_FEED","The response is not an Atom feed.")
    result=[]
    for entry in root.findall("a:entry",ATOM):
        def value(name):
            return " ".join((entry.findtext("a:"+name,default="",namespaces=ATOM)).split())
        url=value("id")
        parsed=urllib.parse.urlparse(url)
        require(parsed.hostname in {"arxiv.org","www.arxiv.org"} and parsed.path.startswith("/abs/"),"INVALID_FEED","Unexpected paper identifier.")
        result.append({"external_id":parsed.path[5:],"url":"https://arxiv.org"+parsed.path,"title":value("title"),"abstract":value("summary"),
                       "published":value("published"),"updated":value("updated"),"authors":[e.findtext("a:name",default="",namespaces=ATOM) for e in entry.findall("a:author",ATOM)]})
    return result


def fetch(query,limit=20):
    require(type(limit) is int and 1<=limit<=100,"INVALID_INPUT","arXiv limit must be 1..100.")
    query=urllib.parse.urlencode({"search_query":query,"start":0,"max_results":limit,"sortBy":"lastUpdatedDate","sortOrder":"descending"})
    request=urllib.request.Request("https://export.arxiv.org/api/query?"+query,headers={"User-Agent":"HermesResearchIdeation/0.1 (research metadata client)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=35) as response:
                require(response.url.startswith("https://export.arxiv.org/"),"INVALID_FEED","Unexpected feed redirect.")
                return parse_feed(response.read(5_000_001))
        except (urllib.error.URLError,TimeoutError,OSError) as exc:
            if attempt==2:
                raise ResearchError("SOURCE_UNAVAILABLE","arXiv is unavailable; no successful update was recorded.",True) from exc
            time.sleep(3*(attempt+1))
