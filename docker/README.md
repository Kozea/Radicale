# Radicale Docker image

This image neither features HTTPS or a webserver. It's recommended to use a 
reverse proxy in front of it.

## Building the image

    cd docker
    make

## Running a container

Radicale can be run in an ephemeral container that mounts the folders `conf` 
and `lib` from the current working directory:

    docker run --rm \
        -v $PWD/lib:/var/lib/radicale \
        -v $PWD/conf:/etc/radicale \
        kozea/radicale:<version>

There's a minimal, working example configuration for Docker Compose in the 
`docker/compose` directory. Copy its contents to a location with a meaningful
name (`radicale` should meet the criteria) change your working directory to it
and run Radicale without attaching stdout:

    docker-compose up -d

## Reference

### Parameters

- `RADICALE_UID`: The user id of the internal radicale user
- `RADICALE_UID`: The group id of the internal radicale group

### Volumes

- `/var/lib/radicale`: data files
- `/etc/radicale`: Radicale configuration (put the configuration file here)

### Ports

- `5323`: Radicale's http port

### Creating a user in a running container

    docker exec -ti --user radicale <ontainer> htpasswd -B -C 16 /etc/radicale/users <username>

A higher value for the `-C` option should increase security, but requires more
computing for authentication. 
