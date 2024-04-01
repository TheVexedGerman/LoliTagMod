#!/bin/bash
# url="localhost:6880/reddit-bots/animemes-modqueue-approver"
# dockerfileName="modque_approver.dockerfile"

# dateTag="$(date +%Y-%m-%d-%H%M)"

# #build + tag docker image
# docker build --pull --no-cache -t $url:latest -t $url:$dateTag -f $dockerfileName .
# #Push all docker image
# docker push --all-tags $url

# #!/bin/bash

url="localhost:6880/reddit-bots/"
imageSuffix="-modque-approver"
# # Make a loop for each docker image in the repo
imageNames=(
    "animemes"
    "hentaimemes"
    )

dateTag="$(date +%Y-%m-%d-%H%M)"
isFirst=true

for imageName in "${imageNames[@]}" ; do
    # Fully build image on first run, afterwards use cache
    if [ "$isFirst" = true ] ; then
        buildParameters="--pull --no-cache"
        isFirst=false
    else
        buildParameters=""
    fi

    # find and replace the dashes to also get the file name from the tag name
    # dockerfileName="$($imageName//-/_)"
    dockerfileName=$(echo "$imageName$imageSuffix" | sed "s/-/_/g")
    #build + tag docker images
    docker build $buildParameters -t $url$imageName$imageSuffix:latest -t $url$imageName$imageSuffix:$dateTag -f $dockerfileName.dockerfile .
    #Push all docker images
    docker push --all-tags $url$imageName$imageSuffix
done