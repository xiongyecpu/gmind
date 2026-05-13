const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("GMindNative", {
  invoke(command, args) {
    return ipcRenderer.invoke(command, args);
  },
  listen(eventName, callback) {
    const listener = (_event, payload) => callback({ payload });
    ipcRenderer.on(eventName, listener);
    return () => ipcRenderer.removeListener(eventName, listener);
  },
});
