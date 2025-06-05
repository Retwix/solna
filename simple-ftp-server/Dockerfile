FROM python:3.9-alpine

# Install pyftpdlib for FTP server
RUN pip install pyftpdlib

# Create upload directory
RUN mkdir -p /home/foo/upload

# Create FTP server script
COPY ftp_server.py /app/ftp_server.py

# Set working directory
WORKDIR /app

# Expose FTP ports
EXPOSE 21 30000-30009

# Run the FTP server
CMD ["python", "ftp_server.py"]
