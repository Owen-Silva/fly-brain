"""Fetch abstracts (and open-access full text when there is one) of the papers the
real-fly facts come from, via the Europe PMC REST API. Saves to data/olfaction/lit/.

Usage: python lit_fetch.py            -> prints id + abstract for each paper
       python lit_fetch.py fulltext PMCID  -> saves the full text XML as plain text
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIT = ROOT / "data" / "olfaction" / "lit"
LIT.mkdir(parents=True, exist_ok=True)

PAPERS = {
    "honegger2011": 'TITLE:"Cellular-resolution population imaging reveals robust sparse coding in the Drosophila mushroom body"',
    "turner2008": 'TITLE:"Olfactory representations by Drosophila mushroom body neurons"',
    "lin2014": 'TITLE:"Sparse, decorrelated odor coding in the mushroom body enhances learned odor discrimination"',
    "bhandawat2007": 'TITLE:"Sensory processing in the Drosophila antennal lobe increases reliability and separability of ensemble odor representations"',
    "olsen2008": 'TITLE:"Lateral presynaptic inhibition mediates gain control in an olfactory circuit"',
    "olsen2010": 'TITLE:"Divisive normalization in olfactory population codes"',
    "campbell2013": 'TITLE:"Imaging a population code for odor identity in the Drosophila mushroom body"',
    "hallem2006": 'TITLE:"Coding of odors by a receptor repertoire"',
    "wilson2004": 'TITLE:"Transformation of olfactory representations in the Drosophila antennal lobe"',
    "murthy2008": 'TITLE:"Testing odor response stereotypy in the Drosophila mushroom body"',
}


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def search(q):
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize=3&query="
           + urllib.parse.quote(q))
    return json.loads(get(url))["resultList"]["result"]


def main():
    out = {}
    for key, q in PAPERS.items():
        try:
            res = search(q)
        except Exception as e:  # noqa: BLE001
            print(key, "ERROR", e)
            continue
        if not res:
            print(key, "no hit")
            continue
        r = res[0]
        rec = {k: r.get(k) for k in ("title", "journalTitle", "pubYear", "pmid", "pmcid", "doi",
                                     "isOpenAccess", "inPMC", "hasTextMinedTerms")}
        rec["authors"] = r.get("authorString", "")[:80]
        rec["abstract"] = re.sub(r"<[^>]+>", "", r.get("abstractText", "") or "")
        out[key] = rec
        print(f"== {key}: {rec['authors'][:40]} {rec['pubYear']} {rec['journalTitle']} "
              f"pmid={rec['pmid']} pmcid={rec['pmcid']} OA={rec['isOpenAccess']}")
    (LIT / "abstracts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def fulltext(pmcid):
    xml = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML")
    txt = re.sub(r"<[^>]+>", " ", xml)
    txt = re.sub(r"\s+", " ", txt)
    p = LIT / f"{pmcid}.txt"
    p.write_text(txt, encoding="utf-8")
    print(p, len(txt), "chars")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "fulltext":
        fulltext(sys.argv[2])
    else:
        main()
