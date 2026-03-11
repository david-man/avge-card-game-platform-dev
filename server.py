from flask import Flask, request, make_response, abort
from flask_socketio import SocketIO, emit, join_room, close_room
from flask_cors import CORS
import threading
from game_host import GameHost
app = Flask(__name__)
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="http://localhost:5173")

#maps current sessions to players. avoids 2 people on same account
sids_to_players = {}

#assume we have an actual db later on lmao
player_db = {"david"}

#maps players to their Game Hosts
player_to_host : dict[str, GameHost]= {}

#Generic Flask stuff
@app.route("/login", methods = ["POST"])
def on_login():
    global player_db, sids_to_players
    data = request.json
    ign = data["ign"]
    pw = data["pw"]
    if(ign not in player_db or ign in sids_to_players.values()):
        abort(401)
    resp = make_response({'success': True}, 200)
    resp.set_cookie('username', ign, samesite = 'Lax')#set to true later
    return resp

@app.route("/logout", methods = ["POST"])
def on_logout():
    resp = make_response(200)
    resp.delete_cookie('username')
    return resp

@app.route("/user_input", methods = ["POST"])
def on_input():
    global player_to_host
    data = request.json
    player_ign = request.cookies.get("username")
    if(player_ign in player_to_host):
        player_to_host[player_ign].input_queues[player_ign].put(data['input'])

@app.route('/start_server')

#Socket IO stuff 
@socketio.on("connect")
def on_connect():
    global player_db
    if('username' in request.cookies):
        emit('connection_confirmation', {'reconnection': True, 'username': request.cookies.get('username')}, to=request.sid)
    else:
        emit('connection_confirmation', {'reconnection': False}, to=request.sid)
@socketio.on('login_confirmation')
def on_confirm():
    global sids_to_players, player_db
    try:
        player_ign = request.cookies.get("username")
        if(player_ign in sids_to_players.values() or player_ign not in player_db):
            abort(401)
        sids_to_players[request.sid] = player_ign
        return 200
    except Exception:
        abort(401)
@socketio.on('disconnect')
def on_disconnect():
    global sids_to_players
    if(request.sid in sids_to_players):
        del sids_to_players[request.sid]

# Run the application
if __name__ == '__main__':
    #start a thread for the server, which manages communications
    threading.Thread(target=lambda : socketio.run(app, host = "localhost", port = 8000), daemon=True).start()

    