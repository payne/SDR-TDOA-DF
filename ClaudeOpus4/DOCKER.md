# Docker
## Docker images

### Docker repository
https://hub.docker.com/r/edgan/sdr-tdoa-df/tags

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

### Running the Docker images
#### Commands
##### dev
`cd SDR-TDOA-DF ; docker run -it --device /dev/bus/usb -v .:/SDR-TDOA-DF edgan/sdr-tdoa-df:dev-0.1 /bin/bash`

1. This command mounts `/dev/bus/usb` for accessing USB devices, like a RTL-SDR.
2. Mounts your `SDR-TDOA-DF` git repository in the  to `/SDR-TDOA-DF` in the Docker container.
3. Any data generated within the docker image, but written to `/SDR-TDOA-DF` will still be there when you close the Docker container, within your `SDR-TDOA-DF` git repository directory.

##### release
`docker run -it --device /dev/bus/usb edgan/sdr-tdoa-df:release-0.1 /bin/bash`

1. This command mounts `/dev/bus/usb` for accessing USB devices, like a RTL-SDR.
2. Any data generated within the docker image, but written to `/SDR-TDOA-DF` will go poof when you close the Docker container.
