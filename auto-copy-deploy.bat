@echo off
echo ================================================
echo  Sick Of It - Copy Deployment Files to EC2
echo ================================================

echo Copying deployment files to EC2 server...
echo Server: ubuntu@ec2-13-220-32-55.compute-1.amazonaws.com
echo.

echo Creating directory on server...
ssh -i sickofitgame-server.pem ubuntu@ec2-13-220-32-55.compute-1.amazonaws.com "mkdir -p ~/sickofitgame"

echo Copying deployment compose file...
scp -i sickofitgame-server.pem docker-compose.deploy.yml ubuntu@ec2-13-220-32-55.compute-1.amazonaws.com:~/sickofitgame/

echo.
echo Deployment file copied successfully!
echo.
echo Files on server:
ssh -i sickofitgame-server.pem ubuntu@ec2-13-220-32-55.compute-1.amazonaws.com "cd ~/sickofitgame && ls -la"

echo.
pause
