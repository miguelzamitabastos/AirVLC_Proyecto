# Entorno de Desarrollo Flutter (macOS)

Esta guía documenta los pasos necesarios para tener tu entorno local listo para desarrollar la futura aplicación móvil de **AirVLC** en Flutter, compilando tanto para iOS como para Android.

## 1. Instalación del SDK de Flutter

Hemos creado un script que automatiza este proceso:
`scripts/install_flutter_mac.sh`

Este script descarga el SDK de Flutter, lo ubica en `~/development/flutter` y actualiza tu `.zshrc`. 
*Si tienes un Mac con chip de Intel en vez de Apple Silicon (M1/M2/M3), tendrás que cambiar el enlace de descarga en el script.*

## 2. Requisitos para iOS (iPhone)

Si quieres probar la app en el simulador de iPhone o en tu propio dispositivo:

1. Instala **Xcode** desde la Mac App Store.
2. Abre Xcode al menos una vez para aceptar los términos y condiciones, o ejecuta en terminal:
   ```bash
   sudo xcodebuild -license
   ```
3. Instala CocoaPods (gestor de dependencias usado por los plugins de Flutter en iOS):
   ```bash
   sudo gem install cocoapods
   ```
   *(Si da error en macOS recientes, usa Homebrew: `brew install cocoapods`)*

## 3. Requisitos para Android

Si quieres compilar para Android:

1. Descarga e instala **Android Studio** (https://developer.android.com/studio).
2. Ábrelo y ve al "SDK Manager" (en Tools > SDK Manager).
3. Asegúrate de instalar el *Android SDK Command-line Tools (latest)*.
4. Acepta las licencias de Android ejecutando en terminal:
   ```bash
   flutter doctor --android-licenses
   ```
   *(Pulsa 'y' a todo).*

## 4. Comprobación Final

Ejecuta en tu terminal:
```bash
flutter doctor
```

El objetivo es que te salgan "ticks" verdes en Flutter, Android toolchain y Xcode. Si Xcode o Android Studio no están configurados, el comando te dirá exactamente qué comandos ejecutar para arreglarlo.
