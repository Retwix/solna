#!/usr/bin/env python3

import os
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

def main():
    # Create authorizer
    authorizer = DummyAuthorizer()
    
    # Add user with read/write permissions
    authorizer.add_user("foo", "pass", "/home/foo/upload", perm="elradfmwMT")
    
    # Create handler
    handler = FTPHandler
    handler.authorizer = authorizer
    
    # Set passive port range
    handler.passive_ports = range(30000, 30010)
    
    # Create server
    server = FTPServer(("0.0.0.0", 21), handler)
    
    # Set max connections
    server.max_cons = 256
    server.max_cons_per_ip = 5
    
    print("Starting FTP server on port 21...")
    print("User: foo, Password: pass")
    print("Upload directory: /home/foo/upload")
    print("Passive ports: 30000-30009")
    
    # Start server
    server.serve_forever()

if __name__ == "__main__":
    main()
