import server, urllib.parse, os

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
    def do_HEAD(self, request):
        response = self.do_GET(request)
        if response.status == 200:
            #TODO: Is this compliant with the standard?
            return server.Response(self.config["VERSION"], 200, "OK",
                headers={
                    "Content-type": response.headers["Content-type"],
                    "Content-length": len(response.content)
                })
        else:
            return response
    def do_GET(self, request):
        if request.uri == "/":
            return self.serve_file("text/html",
                content=IndexTemplate)
        elif request.uri == "/stats":
            return self.serve_file("text/html",
                content=StatsTemplate.format(
                    no_pastes=len(self.pastes))
                )
        return self.get_paste(request.uri[1:])
    def get_paste(self, id):
        try:
            paste_id = int(id)
            paste_content = self.pastes[paste_id]
            paste_content = html_encode(paste_content)
            return self.serve_file("text/html",
                content=PasteTemplate.format(
                    paste_id=paste_id,
                    paste_content=paste_content)
                )
        except (ValueError, IndexError):
            return self.make_error(404, "Not Found")
    def do_POST(self, request):
        if request.uri == "/":
            data = urllib.parse.parse_qs(request.content.decode())
            paste_id = self.create_paste("".join(data["paste"]))
            return self.make_redirect("/{0}".format(paste_id))
        return self.make_error(400, "Bad Request")
    def create_paste(self, data):
        self.pastes.append(data)
        return len(self.pastes) - 1

class PersistentPastebin(Pastebin):
    def __init__(self, *args, **kwargs):
        super(PersistentPastebin, self).__init__(*args, **kwargs)
    def get_paste(self, id):
        try:
            paste_id = int(id)
            with open(os.path.join(self.basedir, "%s" % paste_id)) as file:
                paste_content = html_encode(file.read())
            return self.serve_file("text/html",
                content=PasteTemplate.format(
                    paste_id=paste_id,
                    paste_content=paste_content)
                )
        except (ValueError, FileNotFoundError):
            return self.make_error(404, "Not Found")
    def create_paste(self, data):
        with open(os.path.join(self.basedir, "ID"), "r") as id_file:
            try:
                paste_id = int(id_file.read())
            except ValueError:
                paste_id = 0
        with open(os.path.join(self.basedir, "ID"), "w") as id_file:
            id_file.write(str(paste_id + 1))
        with open(os.path.join(self.basedir, "%s" % paste_id), "w") as file:
            file.write(data)
        return paste_id

if __name__ == "__main__":
    PersistentPastebin(address="", port=8888).serve_forever()