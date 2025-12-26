sudo dnf install -y htop jq snapd git dnf5-plugins

sudo ln -s /var/lib/snapd/snap /snap

sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo

sudo dnf install -y gh

git config --global init.defaultBranch main
git config --global user.email "aguseranieri@gmail.com"
git config --global user.name "Agustin Ranieri"
git config --global credential.username "RaniAgus"
git config --global gpg.format ssh
