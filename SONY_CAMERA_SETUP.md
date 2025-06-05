# Sony Camera FTP Setup Guide

This guide will help you configure your Sony camera to automatically upload photos to the Solna file monitoring application via FTP.

## 📋 Prerequisites

1. **Solna application running** with the FTP service enabled
2. **Sony camera** with FTP/WiFi capabilities (most modern Sony cameras support this)
3. **Same WiFi network** for both your computer running Solna and your Sony camera

## 🔧 Solna FTP Server Configuration

The Solna application is now configured with an FTP server using these settings:

- **Server Address**: `localhost` (or your computer's IP address)
- **Port**: `21`
- **Username**: `foo`
- **Password**: `pass`
- **Upload Directory**: `/home/foo/upload`

## 📷 Sony Camera Configuration Steps

### Step 1: Enable WiFi on Your Camera

1. Go to **Menu** → **Network** → **Wi-Fi Settings**
2. Enable **Wi-Fi Function**
3. Connect to your home WiFi network
4. Note down your camera's IP address (usually shown in network settings)

### Step 2: Configure FTP Settings

1. Navigate to **Menu** → **Network** → **FTP Transfer Function**
2. Set **FTP Transfer Function** to **On**
3. Configure the following settings:

#### FTP Server Settings:
- **Server Name**: `Solna-FTP` (or any name you prefer)
- **Host Name**: `[YOUR_COMPUTER_IP]` (find this using `ipconfig` on Windows or `ifconfig` on Mac/Linux)
- **Port**: `21`
- **User Name**: `foo`
- **Password**: `pass`
- **Directory**: `/home/foo/upload`

#### Transfer Settings:
- **Transfer Target**: Choose what to upload (RAW+JPEG, JPEG only, etc.)
- **Transfer Mode**: **Auto** (uploads immediately after shooting)
- **File Format**: Keep your preferred format

### Step 3: Test the Connection

1. In your camera's FTP settings, look for **Test Connection** or **Connection Test**
2. Run the test to verify the camera can connect to your Solna FTP server
3. You should see a success message if everything is configured correctly

## 🖥️ Finding Your Computer's IP Address

### On macOS:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### On Windows:
```cmd
ipconfig | findstr IPv4
```

### On Linux:
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

## 🧪 Testing the Setup

1. **Start Solna**: Run `docker-compose up` in your Solna directory
2. **Take a test photo** on your Sony camera
3. **Check the logs**: Run `docker-compose logs -f watcher` to see file detection
4. **Verify in database**: The file metadata should be automatically logged

You can also use the provided test script:
```bash
./test-ftp-upload.sh
```

## 🔍 Troubleshooting

### Camera Can't Connect to FTP Server
- **Check IP address**: Make sure you're using the correct computer IP
- **Check firewall**: Ensure ports 21 and 30000-30009 are open
- **Check network**: Both devices must be on the same WiFi network
- **Restart services**: Try `docker-compose down && docker-compose up`

### Files Upload But Aren't Detected
- **Check file watcher logs**: `docker-compose logs watcher`
- **Check API logs**: `docker-compose logs api`
- **Verify directory mapping**: Files should appear in `local_data/` folder

### Permission Issues
- **Check directory permissions**: Ensure `local_data/` is writable
- **Check Docker volumes**: Restart Docker if volume mounting fails

## 📁 File Organization

Uploaded photos will be stored in:
- **Local directory**: `./local_data/`
- **Database**: File metadata logged in PostgreSQL
- **API access**: Available via the web interface at http://localhost:3001

## 🔒 Security Notes

**For Development/Local Use Only**: The current FTP configuration uses simple authentication and is intended for local development. For production use, consider:

- Using FTPS (FTP over SSL/TLS)
- Implementing stronger authentication
- Restricting network access
- Using VPN for remote access

## 📞 Support

If you encounter issues:
1. Check the Docker logs: `docker-compose logs`
2. Verify network connectivity between camera and computer
3. Ensure all services are running: `docker-compose ps`
4. Test with the provided test script: `./test-ftp-upload.sh`
