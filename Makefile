app_name = variantis

build:
	@rm -rf results/
	@docker build -t $(app_name) . 

run:
	@mkdir -p /media/disk0/database/logs/
#	@docker run --detach -v /media/disk0/database/logs:/logs -v /tmp/rrnadb.sock:/dev/shm/rrnadb.sock $(app_name) 
	@docker run --detach -v /tmp/:/tmp/ $(app_name)
	@sleep 10
	@chown :www-data /tmp/variantis.sock

kill:
	@echo 'Killing container...'
	@docker ps | grep $(app_name) | awk '{print $$1}' | xargs docker
