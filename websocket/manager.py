# from fastapi import WebSocket, WebSocketDisconnect
# import json
# import logging
# from typing import List, Dict
# from auth.jwt_handler import verify_token

# logger = logging.getLogger(__name__)

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: List[WebSocket] = []
#         self.user_connections: Dict[str, WebSocket] = {}
    
#     async def connect(self, websocket: WebSocket, token: str = None):
#         await websocket.accept()
        
#         # Optionally authenticate WebSocket connection
#         if token:
#             username = verify_token(token)
#             if username:
#                 self.user_connections[username] = websocket
        
#         self.active_connections.append(websocket)
#         logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
#     def disconnect(self, websocket: WebSocket):
#         if websocket in self.active_connections:
#             self.active_connections.remove(websocket)
        
#         # Remove from user connections
#         for username, ws in list(self.user_connections.items()):
#             if ws == websocket:
#                 del self.user_connections[username]
#                 break
        
#         logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
#     async def send_personal_message(self, message: str, websocket: WebSocket):
#         try:
#             await websocket.send_text(message)
#         except:
#             self.disconnect(websocket)
    
#     async def send_to_user(self, username: str, message: dict):
#         if username in self.user_connections:
#             try:
#                 await self.user_connections[username].send_text(
#                     json.dumps(message, default=str)
#                 )
#             except:
#                 self.disconnect(self.user_connections[username])
    
#     async def broadcast(self, message: dict):
#         disconnected = []
#         for websocket in self.active_connections:
#             try:
#                 await websocket.send_text(json.dumps(message, default=str))
#             except:
#                 disconnected.append(websocket)
        
#         # Remove disconnected websockets
#         for ws in disconnected:
#             self.disconnect(ws)

# manager = ConnectionManager()

# async def websocket_endpoint(websocket: WebSocket, token: str = None):
#     await manager.connect(websocket, token)
    
#     # Add to price service subscribers
#     from main import app
#     app.state.price_service.add_subscriber(websocket)
    
#     try:
#         while True:
#             # Listen for client messages (e.g., subscribe to specific symbols)
#             data = await websocket.receive_text()
#             message = json.loads(data)
            
#             if message.get("type") == "subscribe":
#                 # Handle subscription logic if needed
#                 symbols = message.get("symbols", [])
#                 await websocket.send_text(json.dumps({
#                     "type": "subscription_confirmed",
#                     "symbols": symbols
#                 }))
            
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         app.state.price_service.remove_subscriber(websocket)
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#         manager.disconnect(websocket)
#         app.state.price_service.remove_subscriber(websocket)





from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
from typing import List, Dict
from auth.jwt_handler import verify_token

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, token: str = None):
        await websocket.accept()
        
        # Optionally authenticate WebSocket connection
        # if token:
        #     username = verify_token(token)
        #     if username:
        #         self.user_connections[username] = websocket
        
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from user connections
        for username, ws in list(self.user_connections.items()):
            if ws == websocket:
                del self.user_connections[username]
                break
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def send_to_user(self, username: str, message: dict):
        if username in self.user_connections:
            try:
                await self.user_connections[username].send_text(
                    json.dumps(message, default=str)
                )
            except:
                self.disconnect(self.user_connections[username])
    
    async def broadcast(self, message: dict):
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message, default=str))
            except:
                disconnected.append(websocket)
        
        # Remove disconnected websockets
        for ws in disconnected:
            self.disconnect(ws)

manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket, token: str = None):
    await manager.connect(websocket, token)
    
    # Add to price service subscribers
    from main import app
    app.state.price_service.add_subscriber(websocket)
    
    try:
        while True:
            # Listen for client messages (e.g., subscribe to specific symbols)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe":
                # Handle subscription logic if needed
                symbols = message.get("symbols", [])
                await websocket.send_text(json.dumps({
                    "type": "subscription_confirmed",
                    "symbols": symbols
                }))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        app.state.price_service.remove_subscriber(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        app.state.price_service.remove_subscriber(websocket)
