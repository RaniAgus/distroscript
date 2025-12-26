echo "Installing snapd..."

sudo dnf install -y htop jq snapd

sudo ln -s /var/lib/snapd/snap /snap
