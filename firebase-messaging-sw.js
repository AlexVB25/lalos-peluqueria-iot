importScripts(
  "https://www.gstatic.com/firebasejs/12.3.0/firebase-app-compat.js"
);

importScripts(
  "https://www.gstatic.com/firebasejs/12.3.0/firebase-messaging-compat.js"
);


firebase.initializeApp({

  apiKey:
    "AIzaSyA84RYy5B44TvEya4owbxXpmfuOOCgh3CU",

  authDomain:
    "peluqueria-iot.firebaseapp.com",

  projectId:
    "peluqueria-iot",

  storageBucket:
    "peluqueria-iot.firebasestorage.app",

  messagingSenderId:
    "818035409829",

  appId:
    "1:818035409829:web:1155aa2ae7a6a47b3b9e4c"

});


const messaging =
  firebase.messaging();


// No usamos showNotification() aquí.
// Firebase mostrará automáticamente
// las notificaciones enviadas con
// payload "notification".

messaging.onBackgroundMessage(
  (payload) => {

    console.log(
      "Mensaje recibido en segundo plano:",
      payload
    );

  }
);