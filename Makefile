## https://binx.io/blog/2017/10/07/makefile-for-docker-images/

REGISTRY_HOST=registry.hub.docker.com
USERNAME=$(USER)
NAME=$(shell basename $(CURDIR))
REGISTRY_PROJECT=jsenecal
RELEASE_SCRIPT := $(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))/.make-release.sh
IMAGE=$(REGISTRY_HOST)/$(REGISTRY_PROJECT)/$(NAME)

VERSION=$(shell . $(RELEASE_SCRIPT) ; getVersion)
MAJORVERSION=$(shell . $(RELEASE_SCRIPT) ; getMajorVersion)
MINORVERSION=$(shell . $(RELEASE_SCRIPT) ; getMinorVersion)
TAG=$(shell . $(RELEASE_SCRIPT); getTag)

SHELL=/bin/bash

DOCKER_BUILD_CONTEXT=.
DOCKER_FILE_PATH=Dockerfile

.PHONY: pre-build docker-build post-build build release patch-release minor-release major-release tag check-status check-release showver \
	push pre-push do-push post-push

build: pre-build docker-build post-build

pre-build:


post-build:


pre-push:


post-push:



docker-build: .release
	docker build $(DOCKER_BUILD_ARGS) -t $(IMAGE):$(VERSION) $(DOCKER_BUILD_CONTEXT) -f $(DOCKER_FILE_PATH)
	@DOCKER_MAJOR=$(shell docker -v | sed -e 's/.*version //' -e 's/,.*//' | cut -d\. -f1) ; \
	DOCKER_MINOR=$(shell docker -v | sed -e 's/.*version //' -e 's/,.*//' | cut -d\. -f2) ; \
	if [ $$DOCKER_MAJOR -eq 1 ] && [ $$DOCKER_MINOR -lt 10 ] ; then \
		echo docker tag -f $(IMAGE):$(VERSION) $(IMAGE):latest ;\
		docker tag -f $(IMAGE):$(VERSION) $(IMAGE):latest ;\
		echo docker tag -f $(IMAGE):$(VERSION) $(IMAGE):$(MAJORVERSION) ;\
		docker tag -f $(IMAGE):$(VERSION) $(IMAGE):$(MAJORVERSION) ;\
		echo docker tag -f $(IMAGE):$(VERSION) $(IMAGE):$(MINORVERSION) ;\
		docker tag -f $(IMAGE):$(VERSION) $(IMAGE):$(MINORVERSION) ;\
	else \
		echo docker tag $(IMAGE):$(VERSION) $(IMAGE):latest ;\
		docker tag $(IMAGE):$(VERSION) $(IMAGE):latest ; \
		echo docker tag $(IMAGE):$(VERSION) $(IMAGE):$(MAJORVERSION) ;\
		docker tag $(IMAGE):$(VERSION) $(IMAGE):$(MAJORVERSION) ; \
		echo docker tag $(IMAGE):$(VERSION) $(IMAGE):$(MINORVERSION) ;\
		docker tag $(IMAGE):$(VERSION) $(IMAGE):$(MINORVERSION) ; \
	fi

.release:
	@echo "release=0.0.0" > .release
	@echo "tag=$(NAME)-0.0.0" >> .release
	@echo INFO: .release created
	@cat .release


release: check-status check-release build push


push: pre-push do-push post-push 

do-push: 
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):$(MINORVERSION)
	docker push $(IMAGE):$(MAJORVERSION)
	docker push $(IMAGE):latest

snapshot: build push

showver: .release
	@. $(RELEASE_SCRIPT); getVersion

tag-patch-release: VERSION := $(shell . $(RELEASE_SCRIPT); nextPatchLevel)
tag-patch-release: .release tag 

tag-minor-release: VERSION := $(shell . $(RELEASE_SCRIPT); nextMinorLevel)
tag-minor-release: .release tag 

tag-major-release: VERSION := $(shell . $(RELEASE_SCRIPT); nextMajorLevel)
tag-major-release: .release tag 

patch-release: tag-patch-release release
	@echo $(VERSION)

minor-release: tag-minor-release release
	@echo $(VERSION)

major-release: tag-major-release release
	@echo $(VERSION)


tag: TAG=$(shell . $(RELEASE_SCRIPT); getTag $(VERSION))
tag: check-status
	@. $(RELEASE_SCRIPT) ; ! tagExists $(TAG) || (echo "ERROR: tag $(TAG) for version $(VERSION) already tagged in git" >&2 && exit 1) ;
	@. $(RELEASE_SCRIPT) ; setRelease $(VERSION)
	git add .
	git commit -m "bumped to version $(VERSION)" ;
	git tag $(TAG) ;
	@ if [ -n "$(shell git remote -v)" ] ; then git push --tags ; else echo 'no remote to push tags to' ; fi

check-status:
	@. $(RELEASE_SCRIPT) ; ! hasChanges || (echo "ERROR: there are still outstanding changes" >&2 && exit 1) ;

check-release: .release
	@. $(RELEASE_SCRIPT) ; tagExists $(TAG) || (echo "ERROR: version not yet tagged in git. make [minor,major,patch]-release." >&2 && exit 1) ;
	@. $(RELEASE_SCRIPT) ; ! differsFromRelease $(TAG) || (echo "ERROR: current directory differs from tagged $(TAG). make [minor,major,patch]-release." ; exit 1)
