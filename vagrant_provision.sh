#!/bin/bash
HOME=/home/vagrant

# Remove monitoring container
docker stop cadvisor
docker rm cadvisor
docker rmi google/cadvisor
docker rmi diogomonica/docker-bench-security
docker rmi weaveworks/weavedb
docker rmi swarm
rm /etc/init/cadvisor.conf

# Set commands after logon
cat << EOF > $HOME/.profile
. ~/.bashrc
cd /vagrant
while [ ! -e ~/.docker/config.json ] ; do
	echo
	echo
	echo -e "\e[0;36mDocker Registry login\e[m"
	echo -e "\e[0;33mdocker login \e[m"
	echo
	docker login
done
EOF

# Aliases for docker compose
cat << EOF > $HOME/.bash_aliases
alias dev="sudo sh -c 'echo 1 > /proc/sys/vm/drop_caches'; docker-compose -f dockerfiles/dev/docker-compose.yml"
alias python="dev exec web python"
alias manage="python manage.py"
alias shell="flask shell"
alias clean="docker images --no-trunc | grep '<none>' | awk '{ print \$3 }' | xargs -r docker rmi ; docker ps --filter status=dead --filter status=exited -aq  | xargs docker rm -v ; docker volume ls -qf dangling=true | xargs -r docker volume rm"
alias bash="dev exec web /bin/sh"
alias redis="dev exec web redis-cli"
EOF
