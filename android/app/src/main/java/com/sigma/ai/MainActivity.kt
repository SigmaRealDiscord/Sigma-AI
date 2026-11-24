package com.sigma.ai

import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.Gravity
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var web: WebView
    private val prefs by lazy { getSharedPreferences("sigma", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val saved = prefs.getString("base_url", null)
        if (saved.isNullOrBlank()) showSetup() else openApp(saved)
    }

    private fun showSetup() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(28, 28, 28, 28)
            setBackgroundColor(Color.rgb(15, 17, 24))
        }
        root.addView(TextView(this).apply {
            text = "Sigma AI"
            textSize = 30f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = "Enter the public HTTPS URL of your Sigma AI server."
            textSize = 15f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setPadding(0, 16, 0, 20)
        })
        val input = EditText(this).apply {
            hint = "https://your-sigma-ai-server.com"
            setSingleLine(true)
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }
        root.addView(input, LinearLayout.LayoutParams(-1, -2))
        root.addView(Button(this).apply {
            text = "Connect"
            setOnClickListener {
                val url = input.text.toString().trim().trimEnd('/')
                if (url.startsWith("https://")) {
                    prefs.edit().putString("base_url", url).apply()
                    openApp(url)
                } else input.error = "Use a valid HTTPS URL"
            }
        })
        setContentView(root)
    }

    private fun openApp(url: String) {
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    !request.url.scheme.equals("https", true)
            }
            webChromeClient = WebChromeClient()
            loadUrl(url)
        }
        setContentView(web)
    }

    @Deprecated("Deprecated in Android API")
    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
