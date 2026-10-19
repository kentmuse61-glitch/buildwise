# Third-party notices

## `@google/model-viewer` 4.2.0

Buildwise GH vendors `frontend/vendor/model-viewer.min.js` to provide an in-browser viewer for the application's generated GLB concept models.

- Upstream project: <https://github.com/google/model-viewer>
- Package: `@google/model-viewer` 4.2.0
- Package license: Apache-2.0

The distributed bundle retains its own source/license headers, including notices for bundled components. No third-party model assets are bundled with Buildwise GH.

This library only displays a generated concept massing model. It does not make the model an architectural, structural, engineering, or permit drawing.

## `gltf-validator` 2.0.0-dev.3.10

GitHub Actions uses the Khronos glTF Validator to validate a representative generated GLB against the glTF 2.0 specification before accepting changes.

- Upstream project: <https://github.com/KhronosGroup/glTF-Validator>
- License: Apache-2.0
- Used only in continuous integration; it is not included in the deployed web service.
