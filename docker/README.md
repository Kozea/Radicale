# Radicale docker image

# Build the image

1. Change into the root directory of the repo.
1. `docker build -t radicale .`

# Running the image

```bash
docker run --rm \
    -v $PWD/lib:/var/lib/radicale \
    -v $PWD/conf:/etc/radicale:ro \
    radicale
```

This image neither features HTTPS or a webserver. It's recommended to use a reverse proxy in front of it.

# Reference

## Parameters

- `RADICALE_UID`: The user id of the internal radicale user
- `RADICALE_UID`: The group id of the internal radicale group

## Volumes

- `/var/lib/radicale`: data files
- `/etc/radicale`: Radicale configuration (put the configuration file here)

## Ports

- `5323`: Main radicale port
