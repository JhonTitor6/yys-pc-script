using System;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace YysWebView2ShellPoc
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            bool smokeMode = Array.IndexOf(args, "--smoke") >= 0;
            using (var form = new ShellForm(smokeMode))
            {
                Application.Run(form);
                return form.ExitCode;
            }
        }
    }

    internal sealed class ShellForm : Form
    {
        private readonly WebView2 _webView = new WebView2();
        private readonly bool _smokeMode;
        private readonly Timer _smokeTimeout = new Timer();
        private Uri _pageUri;

        public int ExitCode { get; private set; }

        public ShellForm(bool smokeMode)
        {
            _smokeMode = smokeMode;
            ExitCode = smokeMode ? 1 : 0;
            Text = "WebView2 Shell POC";
            StartPosition = FormStartPosition.CenterScreen;
            Width = 900;
            Height = 650;
            _webView.Dock = DockStyle.Fill;
            Controls.Add(_webView);
            Load += InitializeWebView;

            _smokeTimeout.Interval = 10000;
            _smokeTimeout.Tick += OnSmokeTimeout;
            if (_smokeMode)
            {
                ShowInTaskbar = false;
                Opacity = 0;
            }
        }

        private async void InitializeWebView(object sender, EventArgs e)
        {
            try
            {
                string runtimeVersion = CoreWebView2Environment.GetAvailableBrowserVersionString();
                string userDataFolder = Path.Combine(Path.GetTempPath(), "yys-webview2-shell-poc");
                CoreWebView2Environment environment = await CoreWebView2Environment.CreateAsync(null, userDataFolder);
                await _webView.EnsureCoreWebView2Async(environment);

                _pageUri = new Uri(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "index.html"));
                _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
                _webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                _webView.CoreWebView2.Settings.AreHostObjectsAllowed = false;
                _webView.CoreWebView2.NavigationStarting += OnNavigationStarting;
                _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
                Text = "WebView2 Shell POC — " + runtimeVersion;
                _webView.CoreWebView2.Navigate(_pageUri.AbsoluteUri);

                if (_smokeMode)
                {
                    _smokeTimeout.Start();
                }
            }
            catch (Exception error)
            {
                Fail(error);
            }
        }

        private void OnNavigationStarting(object sender, CoreWebView2NavigationStartingEventArgs e)
        {
            if (_pageUri == null || !string.Equals(e.Uri, _pageUri.AbsoluteUri, StringComparison.OrdinalIgnoreCase))
            {
                e.Cancel = true;
            }
        }

        private void OnWebMessageReceived(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            if (_pageUri == null || !string.Equals(e.Source, _pageUri.AbsoluteUri, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            string message;
            try
            {
                message = e.TryGetWebMessageAsString();
            }
            catch (Exception)
            {
                return;
            }

            switch (message)
            {
                case "ready":
                    _webView.CoreWebView2.PostWebMessageAsString("ping");
                    break;
                case "ping":
                    _webView.CoreWebView2.PostWebMessageAsString("pong");
                    break;
                case "pong":
                    Text = "WebView2 Shell POC — 双向消息正常";
                    if (_smokeMode)
                    {
                        _smokeTimeout.Stop();
                        ExitCode = 0;
                        WriteSmokeLog("PASS");
                        Close();
                    }
                    break;
                case "minimize":
                    WindowState = FormWindowState.Minimized;
                    break;
                case "toggle-maximize":
                    WindowState = WindowState == FormWindowState.Maximized
                        ? FormWindowState.Normal
                        : FormWindowState.Maximized;
                    break;
                case "close":
                    Close();
                    break;
            }
        }

        private void OnSmokeTimeout(object sender, EventArgs e)
        {
            Fail(new TimeoutException("WebView2 消息往返在 10 秒内未完成。"));
        }

        private void Fail(Exception error)
        {
            ExitCode = 1;
            if (_smokeMode)
            {
                WriteSmokeLog(error.ToString());
                Close();
                return;
            }

            MessageBox.Show(error.ToString(), "WebView2 Shell POC 启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }

        private static void WriteSmokeLog(string text)
        {
            try
            {
                File.WriteAllText(Path.Combine(Path.GetTempPath(), "yys-webview2-shell-poc-smoke.log"), text);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
