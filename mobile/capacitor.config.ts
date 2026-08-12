import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  // Preserve the existing Android application ID so V2 upgrades in place.
  appId: 'com.focuscalendar.couple',
  appName: '研序 YanXu',
  webDir: '../mobile_web_build',
  android: {
    backgroundColor: '#eef5f3'
  },
  plugins: {
    LocalNotifications: {
      smallIcon: 'ic_stat_calendar',
      iconColor: '#176b61'
    }
  }
}

export default config
