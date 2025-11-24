//@api-1.0
//
// "Scripts" is a way to enhance Draw Things experience with custom JavaScript snippets. Over time,
// we will enhance Scripts with more APIs and do neccessary modifications on the said APIs, but we
// will also keep the API stable. In particular, you can mark your script with a particular API
// version and it will make sure we use the proper API toolchain to execute the script even in
// the future some of the APIs changed.
//
// Existing APIs:
//
// We currently provides three global objects for you to interact with: `canvas`, `pipeline` and `filesystem`.
//
// `canvas` is the object to manipulate the existing infinite canvas on Draw Things interface. It
// supports the following methods:
//
// `canvas.boundingBox`: return the bounding box of existing images collectively on the canvas.
// `canvas.clear()`: remove all images on the canvas, same effect as you tap on the "New Canvas" button.
// `canvas.clip(listOfTexts)`: return the list of clip scores based on the current canvas image.
// `canvas.createMask(width, height, value)`: create a mask with a given size and fill-in value.
// `canvas.currentMask`: return the current mask on the view, you can further manipulate the mask through `Mask` APIs.
// `mask.src`: return the mask png encoded base 64 string, Ex: "data:image/png;base64,<base 64 encoded image string>"
// `canvas.foregroundMask`: return the mask that corresponding to the foreground of the image using foreground-background segementation model builtin to the app.
// `canvas.backgroundMask`: return the mask that corresponding to the background of the image using foreground-background segementation model builtin to the app.
// `canvas.bodyMask(types, extraArea)`: return the mask that corresponding to the human body of the image using body segementation model builtin to the app. supported types "upper body", "lower body" , "neck" and "dresses", extraArea will make the mask slightly larger. Ex: "canvas.bodyMask(["upper", "dresses"], true)"
// `canvas.loadImage(file)`: load image from a file (a path).
// `canvas.loadImageSrc(src)`: load image from src content similar to html <img> src.
// Supported src content types: "data:image/png;base64," "data:image/jpeg;base64," "data:image/webp;base64," "file://"
// Ex: "data:image/png;base64,<base 64 encoded image string>", or "file://" + filesystem.pictures.path + "/filename"
// `canvas.moveCanvas(left, top)`: move the canvas to a particular coordinate, these coordinates work as if the zoom scale is 1x.
// `canvas.moveCanvas(rect)`: move the canvas to a particular rectangle, this function will move and zoom the canvas to a particular rectangle with x, y, width, height properties.
// `canvas.saveImage(file, visibleRegionOnly)`: save the image currently on canvas to a file.
// `canvas.saveImageSrc(visibleRegionOnly)`: save the image currently on canvas to a src string.
// `canvas.canvasZoom`: Set / get the zoom scale of the canvas.
// `canvas.topLeftCorner`: return the coordinate the canvas currently at, these coordinates work as if the zoom scale is 1x.
// `canvas.updateCanvasSize(configuration)`: extract the size from configuration object and then sync the canvas with that size.
// `canvas.loadMaskFromPhotos()`: load mask from photo picker. It's one of a family of functions in the format of load[layer_name]FromPhotos.
// Possible layer names: Mask, DepthMap, Scribble, Pose, Color, CustomLayer, Moodboard. Ex: loadDepthMapFromPhotos()
// `canvas.loadMaskFromFiles()`: load mask from file picker. It's one of a family of functions in the format of load[layer_name]FromFiles.
// Possible layer names: Mask, DepthMap, Scribble, Pose, Color, CustomLayer, Moodboard. Ex: loadDepthMapFromFiles()
// `canvas.loadMaskFromSrc(srcContent)`: load mask from src content similar to html <img> src.
// Supported src content types: "data:image/png;base64," "data:image/jpeg;base64," "data:image/webp;base64," "file://"
// Ex: "data:image/png;base64,<base 64 encoded image string>", or "file://" + filesystem.pictures.path + "/filename"
// It's one of a family of functions in the format of load[layer_name]FromSrc.
// Possible layer names: Mask, DepthMap, Scribble, Pose, Color, CustomLayer, Moodboard. Ex: loadDepthMapFromSrc(srcContent)
// loadPoseFromJson(jsonString) load pose from json string
// canvas.detectFaces() returns an array of squares containing the faces
//
// We also provides several class for you to better interact with Canvas. `Rectangle`, `Mask`, `Point`, 'ImageMetadata`.
//
// `Point` Class representing a point in 2D space. Ex. "const point = Point(x,y)", "point.x", "point.y"
// `Rectangle` Class representing a rectangle with x, y coordinates, width, and height. Ex. "const rect = Rectangle(x,y, width, height)", "rect.x", "rect.width"
// `ImageMetadata` Class gives you the api to get the width and height from an image source. Ex. "const imageMetadata = ImageMetadata(srcContent)", "imageMetadata.width", "imageMetadata.height"
// `Mask` Class gives you the api to access the source base64String of a mask, it returns from some canvas api.  "const mask = canvas.foregroundMask", "mask.src", "canvas.loadMaskFromSrc(mask.src)"
//
// `pipeline` is the object to run the image generation pipeline. It supports the following methods:
//
// `pipeline.configuration`: extract the current configuration, whether it is on screen or after pipeline.run.
// `pipeline.findControlByName(name)`: using the display name to find a particular control.
// `pipeline.findLoRAByName(name)`: using the display name to find a particular LoRA.
// `pipeline.downloadBuiltins(names)`: download builtin models / LoRAs / ControlNets / upscalers from Draw Things server.
// `pipeline.areModelsDownloaded(names)`: Whether the give list of models are downloaded and available locally.
// `pipeline.prompts`: return prompt and negativePrompt currently on the screen.
// `pipeline.run({prompt: null, negativePrompt: null, configuration: configuration, mask: null})`: run image generation through
// this API. You can optionally provides prompt / negativePrompt, or it can take prompt from the screen. mask can be provided
// optionally too and sometimes it can be helpful.
//
// `filesystem` provides a simple access to the underlying file system. Note that Draw Things is
// sandboxed so we can only have access to particular directories within the user file system.
//
// `filesystem.pictures.path`: get the path of the pictures folder. It is the system Pictures folder on macOS, and a Pictures
// folder under Draw Things within Files app for iOS / iPadOS.
// `filesystem.pictures.readEntries`: enumerate all the files under the pictures folder.
// `filesystem.readEntries(directory)`: enumerate all the files under a directory (absolute path).
//
// `requestFromUser(title, confirm, construction)` provides a way to construct a simple
// script-driven UI such that you can ask user for inputs to continue the generation. This is useful
// when your script has several configurations you would like user to try out.
//
// How to use: `requestFromUser("A title", "What the bottom-right button should be named", function () { return [] })`.
//
// The construction closure is where you provide a list of widgets you want user to see. There are several builtin ones.
//
// `this.size(width, height, minValue, maxValue)`: a composed image size selector including the width and height slider.
// `this.slider(value, valueType, minValue, maxValue, title)`: a single slider. valueType can be `this.slider.percent`, `this.slider.fractional(k)` or `this.slider.scale`.
// `this.textField(value, placeholder, multiline, height)`: a free-form text field for user input.
// `this.imageField(title, multiSelect)`: a image picker.
// `this.directory()`: a directory picker.
// `this.switch(isOn, title)`: a on / off switch.
// `this.segmented(index, options)`: a segmented control. options should be a list of strings.
// `this.menu(index, options)`: a menu. options should be a list of strings.
// `this.section(title, detail, views)`: a title + detail wrapper. views should be an array of these widgets again.
// `this.plainText(value)`: show a text display.
// `this.image(src, height, selectable)`: show a image display. src can be a string or an array of strings. Later is when selectable is true.
// `this.customTextButton(selectedOption, options)`: show a button with selectable options and allow additional customized text option input
// `this.multiselectButton(selectedOption, options)`: show a button with selectable options
//
// The call to `requestFromUser` is blocking. Until user dismissed the dialogue, the call will
// return an array about user's selection for you to continue.
