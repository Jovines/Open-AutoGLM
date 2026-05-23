package com.android.adbkeyboard;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Collections;
import java.util.Comparator;
import java.util.List;

public class AppListReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!"ADB_LIST_APPS".equals(intent.getAction())) {
            return;
        }

        boolean includeSystem = intent.getBooleanExtra("include_system", false);
        int limit = intent.getIntExtra("limit", 1000);

        String appsJson = buildLaunchableAppsJson(context, includeSystem, limit);

        Bundle result = getResultExtras(true);
        result.putString("apps_json", appsJson);
        setResultExtras(result);
        setResultData(appsJson);
        setResultCode(1);

        Log.i("ADBKeyBoard", "ADB_LIST_APPS result count=" + result.getInt("apps_count", 0));
    }

    private String buildLaunchableAppsJson(Context context, boolean includeSystem, int limit) {
        PackageManager packageManager = context.getPackageManager();
        Intent launcherIntent = new Intent(Intent.ACTION_MAIN, null);
        launcherIntent.addCategory(Intent.CATEGORY_LAUNCHER);

        int queryFlags = 0;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            queryFlags = PackageManager.MATCH_ALL;
        }
        List<ResolveInfo> apps = packageManager.queryIntentActivities(launcherIntent, queryFlags);
        Collections.sort(apps, new Comparator<ResolveInfo>() {
            @Override
            public int compare(ResolveInfo left, ResolveInfo right) {
                String leftLabel = left.loadLabel(packageManager).toString();
                String rightLabel = right.loadLabel(packageManager).toString();
                return leftLabel.compareToIgnoreCase(rightLabel);
            }
        });

        JSONArray result = new JSONArray();
        int maxCount = Math.max(limit, 1);

        for (ResolveInfo info : apps) {
            if (info.activityInfo == null || info.activityInfo.applicationInfo == null) {
                continue;
            }

            ApplicationInfo applicationInfo = info.activityInfo.applicationInfo;
            boolean isSystemApp = (applicationInfo.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
            if (!includeSystem && isSystemApp) {
                continue;
            }

            JSONObject app = new JSONObject();
            try {
                app.put("label", info.loadLabel(packageManager).toString());
                app.put("package", info.activityInfo.packageName);
                app.put("activity", info.activityInfo.name);
                app.put("system", isSystemApp);
                result.put(app);
            } catch (JSONException ignored) {
            }

            if (result.length() >= maxCount) {
                break;
            }
        }

        Bundle output = getResultExtras(true);
        output.putInt("apps_count", result.length());
        setResultExtras(output);

        return result.toString();
    }
}
