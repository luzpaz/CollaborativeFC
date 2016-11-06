# ************************************************************************
# *   Copyright (c) Stefan Troeger (stefantroeger@gmx.net) 2016          *
# *                                                                      *
# *   This library is free software; you can redistribute it and/or      *
# *   modify it under the terms of the GNU Library General Public        *
# *   License as published by the Free Software Foundation; either       *
# *   version 2 of the License, or (at your option) any later version.   *
# *                                                                      *
# *   This library  is distributed in the hope that it will be useful,   *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of     *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the      *
# *   GNU Library General Public License for more details.               *
# *                                                                      *
# *   You should have received a copy of the GNU Library General Public  *
# *   License along with this library; see the file COPYING.LIB. If not, *
# *   write to the Free Software Foundation, Inc., 59 Temple Place,      *
# *   Suite 330, Boston, MA  02111-1307, USA                             *
# ************************************************************************

from PySide import QtCore, QtGui, QtWebKit, QtNetwork
from PySide.QtCore import Qt, QObject, QUrl, Slot
from PySide.QtGui  import QFrame, QGridLayout, QSizeGrip
import FreeCAD


#class PersistantCookieJar(QtNetwork.QNetworkCookieJar()):
#    
#    def __init__(self):
#        super(PersistantCookieJar, self).__init()

class Backend(QObject):
    
    def __init__(self, parent=None):
        super(Backend, self).__init__(parent)
        
    @Slot(str, str)
    def saveLoginData(self, token, profile):
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Collaboration")
        p.SetString("JSONWebToken", token)
        p.SetString("Profile", profile)
        
    @Slot(result=str)
    def getToken(self):
        return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Collaboration").GetString("JSONWebToken")
        
    @Slot(result=str)
    def getProfile(self):
        return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Collaboration").GetString("Profile")

class BrowserWidget(QFrame):
    
    def __init__(self):
        super(BrowserWidget, self).__init__()
        QtWebKit.QWebSettings.globalSettings().setAttribute(QtWebKit.QWebSettings.DeveloperExtrasEnabled, True)
        self.initUI()
        
    def initUI(self):

        # We are a popup, make sure we look like it
        self.setContentsMargins(1,1,1,1)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setGeometry(0, 0, 300, 500)   
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        #setup the webview for the real UI
        hbox = QGridLayout()
        hbox.setContentsMargins(0,0,0,0)
        self.webView = QtWebKit.QWebView()
        self.webView.page().networkAccessManager().setCookieJar( QtNetwork.QNetworkCookieJar() )
        self.webView.loadFinished.connect(self.pageLoaded)
        hbox.addWidget(self.webView)
        self.setLayout(hbox)
        
        #resizable for more usser control
        sizeGrip = QSizeGrip(self);
        hbox.addWidget(sizeGrip, 0,0,1,1, Qt.AlignBottom | Qt.AlignRight)        
        
        #load the real UI
        self.loaded = False
        self.webView.load(QUrl("http://localhost:8000"))  
         
    def pageLoaded(self, ok):
        #install our javascript backend for js<->python communication
        self.webView.page().mainFrame().addToJavaScriptWindowObject('backend', Backend())
         
    def show(self):
        #try to find the correct position for the popup browser
        pos = QtGui.QCursor.pos()
        widget = QtGui.qApp.widgetAt(pos)
        point = widget.rect().bottomLeft()
        global_point = widget.mapToGlobal(point)
        self.move(global_point)
        if not self.loaded:
            self.webView.load(QUrl("http://localhost:8000")) 
            self.loaded = True
            
        super(BrowserWidget, self).show()        
    
        
# provide a singleton for global access
browser = BrowserWidget()