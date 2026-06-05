# OPEA comps/cores standalone libs

This part of common code will be used by several microservices, now let's put them in a standalone python libs projects.
With many advantages, like

* Libs stand as real "lib", and apps stand as real "app", avoid source code copying
* For apps, can use it in a regular way now: dependencies tracking, pip install, import it in code, etc.
* Let the lib track its dependencies(modules) seperately, instead of put all of them into app's requirements
* Then the app's dependencies can be more clean and managable
* Easier to control the content and size of container images
* Easier for apps to remove the libs if need to stop to use it

## Usage

In the project folder, just using ```uv build``` to build the wheel files, which will be in ./dist dir as normal. Then
copying and pip install it anywhere.

If want to use it in current EKBA services, together with container iamge building methods, here is a sample Dockerfile:
```
# Build stage
FROM python:3.12.9-slim as builder

WORKDIR /build
COPY . /build

# Build the wheel
RUN pip install build && \
    python -m build --wheel

# Final stage for this APP
FROM python:3.12.9-slim

WORKDIR /app
# Copy only the wheel file from builder
COPY --from=builder /build/dist/*.whl /app/

# Install the wheel
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir *.whl

# The following parts are APP specified content
...

```