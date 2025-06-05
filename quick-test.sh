#!/bin/bash

echo "🧪 Quick Test of Solna FTP System"
echo "================================"

# Create a test photo file
TEST_FILE="test_photo_$(date +%Y%m%d_%H%M%S).jpg"
echo "📸 Creating test photo: $TEST_FILE"
echo "FAKE JPEG DATA - Test photo taken at $(date)" > "$TEST_FILE"

# Upload via FTP (simulating camera upload)
echo "📤 Uploading via FTP..."
curl -T "$TEST_FILE" ftp://foo:pass@localhost:21/ 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Upload successful!"
    
    # Wait for processing
    echo "⏳ Waiting for file detection..."
    sleep 2
    
    # Check if file was detected
    echo "🔍 Checking database..."
    docker-compose exec -T db psql -U postgres -d photo_storage -c "
    SELECT filename, event, created_at 
    FROM uploaded_files 
    WHERE filename LIKE '%$TEST_FILE%' 
    ORDER BY created_at DESC;" 2>/dev/null
    
    echo ""
    echo "🎉 Test completed! Check the web interface at http://localhost:3001"
else
    echo "❌ Upload failed"
fi

# Cleanup
rm -f "$TEST_FILE"
