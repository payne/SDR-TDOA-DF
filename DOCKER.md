# Docker
## Docker images

### Docker repository
https://hub.docker.com/r/argussdr/sdr-tdoa-df/tags

### dev tag
This is all the build requirements installed in a Ubuntu docker image. It is useful for development, and you can mount in your git repository.

### release tag
This is based on the dev Docker image, but also includes the /SDR-TDOA-DF/ClaudeOpus4 code in /SDR-TDOA-DF.

### Default working directory
The default working directory in the Docker image is `/SDR-TDOA-DF`.

### Timezone
The timezone is set to America/Chicago aka US/Central.

### Building the Docker images
`docker build . -f Dockerfile.dev`
`docker build . -f Dockerfile.release`

### Tagging Docker images
`docker tag <sha256sum> repository/name:tag`

like

```
docker tag 4ecf0bf70a5db58944c904ef85b7ba2878021ed1a9250045fe50884e7f01441d argussdr/sdr-tdoa-df:dev-0.3
docker tag 5d588386ea3dca4e5d8f441aadea3d7d24c636570950ddf1806aae5209319a5d argussdr/sdr-tdoa-df:release-0.3
```

Where `<sha256sum>`, `tag` change each time you create a new Docker image

### Pushing Docker images
```
docker push argussdr/sdr-tdoa-df:dev-0.3
docker push argussdr/sdr-tdoa-df:release-0.3
```

### Running the Docker images
#### Commands
##### dev
`cd SDR-TDOA-DF ; docker run -it --device /dev/bus/usb --mount type=bind,src=.,dst=/SDR-TDOA-DF argussdr/sdr-tdoa-df:dev-0.3 /bin/bash`

1. This command mounts `/dev/bus/usb` for accessing USB devices, like a RTL-SDR.
2. Mounts your `SDR-TDOA-DF` git repository in the  to `/SDR-TDOA-DF` in the Docker container.
3. Any data generated within the docker image, but written to `/SDR-TDOA-DF` will still be there when you close the Docker container, within your `SDR-TDOA-DF` git repository directory.

##### release
`docker run -it --device /dev/bus/usb --mount type=bind,src=./nice_data,dst=/SDR-TDOA-DF/nice_data argussdr/sdr-tdoa-df:release-0.3 ./sync_collect_samples.py`
`docker run -it --device /dev/bus/usb --mount type=bind,src=./nice_data,dst=/SDR-TDOA-DF/nice_data argussdr/sdr-tdoa-df:release-0.3 ./tdoa_processor_three_stations.py`

1. This command mounts `/dev/bus/usb` for accessing USB devices, like a RTL-SDR.
