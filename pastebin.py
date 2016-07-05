import server, urllib.parse

BaseTemplate = """\
<!doctype html>
<html>
    <head>
        <title>Pastebin{title}</title>
    </head>
    <body>
        {body}
    </body>
</html>
"""

IndexTemplate = BaseTemplate.format(title="", body="""\
        <h1>Pastebin</h1>
        <hr/>
        <form action="/" method="post">
            <textarea name="paste"></textarea><br/>
            <input type="submit" value="Submit">
        </form>
""")

PasteTemplate = BaseTemplate.format(title=" - paste {paste_id}", body="""\
        <h1>Paste {paste_id}</h1>
        <hr/>
        <pre>{paste_content}</pre>
""")

StatsTemplate = BaseTemplate.format(title=" - statistics", body="""\
        <h1>Statistics</h1>
        <hr/>
        <p>{no_pastes} paste(s)</p>
""")

def html_encode(string):
    return string.replace("<", "&lt;").replace(">", "&gt;")

class Pastebin(server.BaseServer):
    def __init__(self, *args, **kwargs):
        super(Pastebin, self).__init__(*args, **kwargs)
        self.pastes = []
    def do_GET(self, request):
        if request.uri == "/":
            return server.Response(self.config["VERSION"], 200, "Ok",
                headers={"Content-type": "text/html"},
                content=IndexTemplate)
        elif request.uri == "/stats":
            return server.Response(self.config["VERSION"], 200, "Ok",
                headers={"Content-type": "text/html"},
                content=StatsTemplate.format(
                    no_pastes=len(self.pastes)))
        return self.get_paste(request.uri[1:])
    def get_paste(self, uri):
        try:
            paste_id = int(uri)
            paste_content = html_encode(self.pastes[paste_id])
            #print(paste_content)
            return server.Response(self.config["VERSION"], 200, "Ok",
                headers={"Content-type": "text/html"},
                content=PasteTemplate.format(
                    paste_id=paste_id,
                    paste_content=paste_content))
        except (ValueError, IndexError):
            return self.make_error(404, "Not Found")
    def do_POST(self, request):
        if request.uri == "/":
            data = urllib.parse.parse_qs(request.content.decode())
            self.pastes.append("".join(data["paste"]))
            return server.Response(self.config["VERSION"], 303, "See Other",
                headers={"Location": "/{0}".format(len(self.pastes)-1)})
        return self.make_error(400, "Bad Request")

if __name__ == "__main__":
    Pastebin(address="", port=8888).serve_forever()