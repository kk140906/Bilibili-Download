# Bilibili Download

- 安装必备模块:
  
    >pip3 install tqdm requests

  **NOTE:** 
   - 1、存在大文件ffmpeg,git clone 可能比较慢,可直接下载release压缩包，
   - 2、在弹幕位置的设定上采用了暴力方法,xml弹幕转ass弹幕可能失败,
   - 3、经简单测试,线程开太多,容易下载失败,目前最多10个线程同时下载。

- 使用方法：

    >usage: python bilibili.py [-h] [-iu url [url ...] | -if url_file] [-dp p  [p ...]]
    >
    >optional arguments:  
    >  ***-h***, --help         &emsp;&emsp;show this help message and exit;   
    >  ***-dp***, p [p ...]      &emsp;&emsp;download play list in a url;  
    >
    >necessary options:  
    >  ***-iu***, url [url ...]  &emsp;&emsp;a serise of url download list;  
    >  ***-if***, url_file       &emsp;&emsp;a file of url download list;  
    > ***-iu -if*** is mutexd,only one option can be used in cmd;  

- 参考例子：
  - input_url,单个url视频下载：

    >python bilibili.py -iu https://www.bilibili.com/bangumi/play/ep95269

  - input_url,多个url视频下载：

    >python bilibili.py -iu https://www.bilibili.com/bangumi/play/ep95269 https://www.bilibili.com/bangumi/play/ep95565

  - input_url_file,下载url_file内的所有url视频,url_file内一个url一行：

    >python bilibili.py -if ./url_file.txt
  - input_url,播放列表下载,下载播放列表内所有视频：

    >python bilibili.py -iu https://www.bilibili.com/bangumi/play/ep95269 -dp all
  - input_url,播放列表下载,下载播放列表内第1、第2至第5及第6个视频：

    >python bilibili.py -iu https://www.bilibili.com/bangumi/play/ep95269 -dp 1 2:5 6

    **NOTE:** 多url下载时,如果同时启用播放列表下载，未包含多p播放列表的url将只下载url的视频，包含多p播放列表的url将按照设定的播放列表下载视频
