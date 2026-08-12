package com.focuscalendar.couple;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

@CapacitorPlugin(name = "YanXuUpdater")
public class UpdatePlugin extends Plugin {
    @com.getcapacitor.PluginMethod
    public void downloadAndInstall(PluginCall call) {
        String url = call.getString("url", "");
        String expected = call.getString("sha256", "").toLowerCase();
        if (!url.startsWith("https://") || !expected.matches("[0-9a-f]{64}")) {
            call.reject("更新地址或 SHA-256 无效"); return;
        }
        getBridge().executeOnMainThread(() -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getContext().getPackageManager().canRequestPackageInstalls()) {
                Intent permission = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getContext().getPackageName()));
                getActivity().startActivity(permission);
                JSObject result = new JSObject(); result.put("status", "permission_required"); call.resolve(result); return;
            }
            new Thread(() -> download(call, url, expected), "YanXu-update-download").start();
        });
    }

    private void download(PluginCall call, String source, String expected) {
        getBridge().getContext().getCacheDir().mkdirs();
        File directory = new File(getBridge().getContext().getCacheDir(), "updates"); directory.mkdirs();
        File partial = new File(directory, "YanXu-update.apk.part");
        File apk = new File(directory, "YanXu-update.apk");
        try {
            HttpURLConnection connection = (HttpURLConnection)new URL(source).openConnection();
            connection.setConnectTimeout(15000); connection.setReadTimeout(60000); connection.setInstanceFollowRedirects(true);
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) throw new Exception("HTTP " + status);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (BufferedInputStream input = new BufferedInputStream(connection.getInputStream()); FileOutputStream output = new FileOutputStream(partial)) {
                byte[] buffer = new byte[65536]; int count;
                while ((count = input.read(buffer)) >= 0) { output.write(buffer, 0, count); digest.update(buffer, 0, count); }
            } finally { connection.disconnect(); }
            StringBuilder actual = new StringBuilder(); for (byte b : digest.digest()) actual.append(String.format("%02x", b));
            if (!actual.toString().equals(expected)) { partial.delete(); call.reject("SHA-256 校验失败，安装包已丢弃"); return; }
            if (apk.exists() && !apk.delete()) { partial.delete(); call.reject("无法清理旧更新缓存"); return; }
            if (!partial.renameTo(apk)) { partial.delete(); call.reject("无法准备安装包"); return; }
            Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", apk);
            Intent install = new Intent(Intent.ACTION_VIEW); install.setDataAndType(uri, "application/vnd.android.package-archive"); install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            getBridge().executeOnMainThread(() -> { getContext().startActivity(install); JSObject result = new JSObject(); result.put("status", "installer_opened"); call.resolve(result); });
        } catch (Exception error) { partial.delete(); call.reject("下载更新失败：" + error.getMessage()); }
    }
}
