import json, sys, urllib.request, os, re
req = json.load(sys.stdin)
key = open(os.path.expanduser("~/.gmi_key")).read().strip()
body = json.dumps({"model": req.get("model", "deepseek-ai/DeepSeek-V3-0324"), "messages": req["messages"], "max_tokens": req.get("max_tokens", 900), "temperature": req.get("temperature", 0.9), "top_p": 0.95}).encode()
r = urllib.request.Request("https://api.gmi-serving.com/v1/chat/completions", body, {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "curl/8.7.1"})
t = json.loads(urllib.request.urlopen(r, timeout=180).read())["choices"][0]["message"]["content"]
print(re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip())
