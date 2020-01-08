import re
import os
import json
import argparse
import requests
import logging
import xml2ass
import subprocess
from time import sleep, time
from common import Download, TqdmLoggingHandler, RunCmdException
from threading import Thread, Lock, current_thread, Semaphore, Condition, local
from concurrent.futures import ThreadPoolExecutor, wait


class Bilibili:

    mainurl = None
    downdir = {"cache": "cache", "downloaded": "downloaded"}
    lockgetplayinfo = Lock()
    tl = local()
    # downcomplete = Condition()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logfile = "{}\\bilibili.log".format(downdir['downloaded'])

    def __init__(self):
        pass

    @staticmethod
    def ArgParse():
        parser = argparse.ArgumentParser()
        group = parser.add_argument_group(title='necessary options')
        mutex = group.add_mutually_exclusive_group()
        mutex.add_argument('-iu',
                           metavar="url",
                           dest="input_url",
                           nargs='+',
                           help='a serise of url download list')
        mutex.add_argument('-if',
                           metavar='url_file',
                           dest="input_url_file",
                           help="a file of url download list")
        parser.add_argument('-dp',
                            metavar='p',
                            dest="down_play_list",
                            nargs='+',
                            help='download play list in a url;')
        return parser

    @staticmethod
    def LogInit(logger, logfile):
        def FormatHandler(handler):
            formatter = logging.Formatter("[%(asctime)s-%(levelname)s](func:%(funcName)s,line:%(lineno)d): %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        handler = logging.StreamHandler()
        FormatHandler(handler)

        handler = logging.FileHandler(logfile)
        FormatHandler(handler)

        # handler = TqdmLoggingHandler()
        # FormatHandler(handler)

    @classmethod
    def MakeDirs(cls):
        for tmepdir in cls.downdir:
            try:
                os.mkdir(tmepdir)
            except FileExistsError:
                pass

    @staticmethod
    def RunCmd(cmd):
        try:
            p_result = subprocess.run(cmd,
                                      capture_output=True,
                                      encoding="GB2312",
                                      shell=True)
            if p_result.stdout:
                return p_result.stdout
            if p_result.stderr:
                raise RunCmdException(p_result.stderr)
        except FileNotFoundError:
            raise RunCmdException("Cmd '{}' can't run in subprocess".format(cmd))

    @staticmethod
    def AttachHeaders(header: dict = None):
        defaultheader = {
            "Connection": "keep-alive",
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if header is not None:
            header.update(defaultheader)
            return header
        else:
            return defaultheader

    @staticmethod
    def ParseWebUrl(url):
        videotype = re.search(r"(?<=com/)(.*?)(?=/)", url).group(0)
        if videotype == 'video':
            result = re.search(r"(.*)(?=\?p=)", url)
            baseurl = url + "?p=" if not result else result.group(0) + "?p="
        elif videotype == 'bangumi':
            baseurl = re.sub(r"\d+", "", url)
        return baseurl, videotype

    @staticmethod
    def ParseHost(url):
        return re.search(r"(?<=://)(.*?)(?=/)", url).group(0)

    @staticmethod
    def ParseVideoNum(url):
        return re.search(r"(?<=\?p=)(\d+)", url).group(0)

    @staticmethod
    def ParseDownList(downlist):
        pairlist = [
            list(range(int(i.split(':')[0]),
                       int(i.split(':')[1]) + 1)) for i in downlist if ':' in i
        ]
        singlelist = [int(i) for i in downlist if ':' not in i]
        return singlelist + sum(pairlist, [])

    @classmethod
    def ResquestMainWeb(cls, url):
        with cls.lockgetplayinfo:
            header = {
                "Host":cls.ParseHost(url),
                "Sec-Fetch-Mode":"navigate",
                "Sec-Fetch-Site":"same-origin",
                "Sec-Fetch-User":"?1",
                "Upgrade-Insecure-Requests":"1",
                "Cookie":"CURRENT_FNVAL=16;CURRENT_QUALITY=80",
            }
            response = requests.get(url, headers=cls.AttachHeaders(header))
            Download.files("{}\\mainweb.html".format(cls.downdir['cache']),response)
            s_videourl = re.search(
                r"(?<=<script>window.__playinfo__=)(.*?)(?=</script><script>)",
                response.text).group(0)
            s_videolist = re.search(
                r"(?<=<script>window.__INITIAL_STATE__=)(.*?)(?=\;\(function\(\)\{)",
                response.text).group(0)
            Download.files("{}\\videourl.json".format(cls.downdir['cache']),s_videourl)
            Download.files("{}\\videolist.json".format(cls.downdir['cache']),s_videolist)
            d_videourl = json.loads(s_videourl)
            d_videolist = json.loads(s_videolist)
            # video audio is separated
            try:
                videourl = d_videourl['data']['dash']['video'][0]['baseUrl']
                audiourl = d_videourl['data']['dash']['audio'][0]['baseUrl']
                cls.tl.av_separated = True
                d_videourl = {1: videourl, 2: audiourl}
            # Segmented video and video audio no separated
            except KeyError:
                cls.tl.av_separated = False
                d_videourl = {videopart['order']:videopart['url'] for videopart in d_videourl['data']['durl']}

            # video
            try:
                videoname = d_videolist['videoData']['title']
                totalvideonums = d_videolist['videoData']['videos']
                if totalvideonums > 1:
                    videoname += '-' + d_videolist['videoData']['pages'][int(cls.ParseVideoNum(url)) - 1]['part']
                d_videoid = {videoid + 1:d_videolist['videoData']['pages'][videoid]['page'] for videoid in range(totalvideonums)}
                cid = d_videolist['videoData']['cid']
            # bangumi
            except KeyError:
                videoname = d_videolist['h1Title']
                totalvideonums = d_videolist['epList'].__len__()
                d_videoid = {videoid + 1: d_videolist['epList'][videoid]['id'] for videoid in range(totalvideonums)}
                cid = d_videolist['epInfo']['cid']
            return videoname, d_videourl,cid,totalvideonums, d_videoid

    @classmethod
    def StartDownVideo(cls, namepath, videourl):
        originhost = cls.ParseHost(cls.mainurl)
        header = {
            "Host": cls.ParseHost(videourl),
            "Origin": "https://{}".format(originhost),
            "Referer": "https://{}".format(originhost),
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }
        reponse = requests.get(videourl,
                               headers=cls.AttachHeaders(header),
                               stream=True)
        Download.streamvideos(namepath, reponse)

    @classmethod
    def DownBarrages(cls,cid,videoname):
        url = "https://api.bilibili.com/x/v1/dm/list.so?oid={}".format(cid)
        header = {
            "Host":cls.ParseHost(url),
            "Sec-Fetch-Mode":"navigate",
            "Sec-Fetch-Site":"same-origin",
            "Sec-Fetch-User":"?1",
            "Upgrade-Insecure-Requests":"1",
            "Cookie":"CURRENT_FNVAL=16;CURRENT_QUALITY=80",
        }
        response = requests.get(url,headers=cls.AttachHeaders(header))
        Download.files('{}\\{}.xml'.format(cls.downdir['cache'],videoname),response,'ISO-8859-1')


    @classmethod
    def DownVideo(cls, d_videourl):
        videonamelist = []
        thread_list = []
        # MultiThread
        # with open("{}\\{}filelist.txt".format(cls.downdir['cache'],cls.tl.threadpoolname),"w+") as file:
        #     for videopart,videourl in d_videourl.items():
        #         t_dwonload = Thread(target = cls.StartDownVideo,kwargs={"namepath":"{}\\{}.mp4".format(cls.downdir['cache'],cls.tl.threadpoolname+str(videopart)),"videourl":videourl})
        #         t_dwonload.setDaemon(True)
        #         thread_list.append(t_dwonload)
        #         videonamelist.append('{}\\{}.mp4'.format(cls.downdir['cache'],cls.tl.threadpoolname+str(videopart)))
        #         t_dwonload.start()
        #         file.writelines("file '{}.mp4'\n".format(cls.tl.threadpoolname+str(videopart)))
        # for tlist in thread_list:
        #     tlist.join()

        # ThreadPool
        with open("{}\\{}filelist.txt".format(cls.downdir['cache'],cls.tl.threadpoolname),"w+") as file:
            with ThreadPoolExecutor(max_workers=5) as pool:
                for videopart, videourl in d_videourl.items():
                    future = pool.submit(
                                        cls.StartDownVideo, "{}\\{}.mp4".format(
                                        cls.downdir['cache'],
                                        cls.tl.threadpoolname + str(videopart)), videourl)
                    videonamelist.append(
                                        '{}\\{}.mp4'.format(
                                        cls.downdir['cache'],
                                        cls.tl.threadpoolname + str(videopart)))
                    thread_list.append(future)
                    file.writelines("file '{}.mp4'\n".format(cls.tl.threadpoolname + str(videopart)))
                    sleep(0.1)
                wait(thread_list)
                pool.shutdown()

        with open("{}\\{}videoname.txt".format(cls.downdir['cache'],cls.tl.threadpoolname),"w+") as file:
            file.write(" ".join(videonamelist))

    @classmethod
    def MergeVideo(cls, videoname):
        # ffmpeg argument use "/",cmd use "//"
        # FIXME:
        if cls.tl.av_separated:
            ffmpegcmd = "ffmpeg_static\\bin\\ffmpeg -loglevel error -i {0}/{1}1.mp4 -i {0}/{1}2.mp4 -c:v copy -c:a aac -y {2}/output{1}.mp4".format(
                cls.downdir['cache'], cls.tl.threadpoolname,
                cls.downdir['downloaded'])
        else:
            ffmpegcmd = "ffmpeg_static\\bin\\ffmpeg -loglevel error -f concat -i {0}/{1}filelist.txt -c copy -y {2}/output{1}.mp4".format(
                cls.downdir['cache'], cls.tl.threadpoolname,
                cls.downdir['downloaded'])

        Bilibili.logger.info("start merge video:{}".format(videoname))

        try:
            mergeinfo = cls.RunCmd(ffmpegcmd)
            if mergeinfo:
                Bilibili.logger.info(mergeinfo)
        except RunCmdException as e:
            Bilibili.logger.error(e)
        else:
            Bilibili.logger.info("merged complete:{}".format(videoname))
            Bilibili.logger.info("start clean...")

        if os.path.exists("{}\\{}.mp4".format(cls.downdir['downloaded'],
                                              videoname)):
            Bilibili.logger.warning("exist video:{}".format(videoname))
            Bilibili.logger.warning("start rename video:{}".format(videoname))
            os.remove("{}\\{}.mp4".format(cls.downdir['downloaded'],
                                          videoname))
        try:
            os.rename(
                "{}\\output{}.mp4".format(cls.downdir['downloaded'],
                                          cls.tl.threadpoolname),
                "{}\\{}.mp4".format(cls.downdir['downloaded'], videoname))
        except OSError:
            Bilibili.logger.error("video rename fail:{}".format(videoname))
        try:
            with open(
                    "{}\\{}videoname.txt".format(cls.downdir['cache'],
                                                 cls.tl.threadpoolname),
                    "r") as file:
                videoliststr = file.read()
        except Exception:
            Bilibili.logger.error("open file fail:{}".format(
                "{}\\{}videoname.txt".format(cls.downdir['cache'],
                                             cls.tl.threadpoolname)))
        try:
            mergeinfo = cls.RunCmd("del {}\\{}filelist.txt {}".format(
                cls.downdir['cache'], cls.tl.threadpoolname, videoliststr))
            mergeinfo = None
            if mergeinfo:
                Bilibili.logger.info(mergeinfo)
        except RunCmdException as e:
            Bilibili.logger.error(e)
        else:
            Bilibili.logger.info("clean complete")

    @classmethod
    def Down(cls, downlist=None):
        """downlist = ['1','3:6','7']
           downlist = 'all'
        ."""
        cls.MakeDirs()
        _, _, _, totalvideonums, d_videoid = cls.ResquestMainWeb(cls.mainurl)
        if totalvideonums == 1 or downlist is None:
            cls.Run(cls.mainurl)
            try:
                cls.RunCmd("cls")
            except RunCmdException as e:
                Bilibili.logger.error(e)

            try:
                cls.RunCmd("rmdir /q /s cache")
            except RunCmdException as e:
                Bilibili.logger.error(e)
        else:
            baseurl, _ = cls.ParseWebUrl(cls.mainurl)
            f_list = []
            with ThreadPoolExecutor(max_workers=2) as pool:
                if downlist == ['all']:
                    down_list = d_videoid
                else:
                    down_list = cls.ParseDownList(downlist)

                for videonum in d_videoid:
                    if videonum in down_list:
                        f = pool.submit(cls.Run, baseurl + "{}".format(d_videoid[videonum]))
                        f_list.append(f)
                        sleep(0.1)
                wait(f_list)
                pool.shutdown()
                try:
                    cls.RunCmd("cls")
                except RunCmdException as e:
                    Bilibili.logger.error(e)

                try:
                    cls.RunCmd("rmdir /q /s cache")
                except RunCmdException as e:
                    Bilibili.logger.error(e)
        # Bilibili.logger.info("all video download complete")


    @staticmethod
    def ParseXml(assfile,xmlfile):
        xmlparser = xml2ass.GenerateAss(assfile,xmlfile)
        xmlparser.run()

    @classmethod
    def Run(cls, url):
        videoname, d_videourl, cid, _, _,= cls.ResquestMainWeb(url)
        videoname = re.sub(r"[\\\/\:\*\?\"\<\>\|]+", "-", videoname)
        cls.tl.threadpoolname = current_thread().name
        Bilibili.logger.info("start download:{}".format(videoname))
        cls.DownBarrages(cid,videoname)
        st_download  = '{}\\{}.ass'.format(cls.downdir['downloaded'],videoname)
        st_cache = '{}\\{}.xml'.format(cls.downdir['cache'],videoname)
        try:
            t_ass = Thread(target=cls.ParseXml,args=(st_download,st_cache))
            t_ass.start()
            t_ass.join(5)
        except RuntimeError:
            Bilibili.logger.error('xml barrages conver to ass failed:{}'.format(videoname))
        sleep(1)
        cls.DownVideo(d_videourl)
        Bilibili.logger.info("download complete:{}".format(videoname))
        cls.MergeVideo(videoname)


    @classmethod
    def Main(cls,debug_url = None,debug_downlist = None):
        cls.MakeDirs()
        cls.LogInit(cls.logger, cls.logfile)
        if not debug_url:
            parser = cls.ArgParse()
            args = parser.parse_args()
            if args.input_url:
                url_list = args.input_url
            elif args.input_url_file:
                try:
                    with open(args.input_url_file, 'r') as file:
                        url_list_temp = file.readlines()
                        url_list = [re.sub(r"\s",'',url) for url in url_list_temp]
                except Exception as e:
                    Bilibili.logger.error(e)
                    return
            else:
                Bilibili.logger.error('input correct necessary options and retry')
                return
        else:
            url_list = debug_url
        if not debug_downlist:
            if args.down_play_list:
                for dp in args.down_play_list:
                    if re.findall(r"[^\d\:]", dp) and dp != 'all':
                        Bilibili.logger.error('uncorrect download play list')
                        return
                    elif dp == 'all' and args.down_play_list.__len__() > 1:
                        Bilibili.logger.error('uncorrect download play list')
                        return
            down_list = args.down_play_list 
        else:
            down_list = debug_downlist
        for url in url_list:
            if not url.startswith('https://www.'):
                url = 'https://www.' + url
            cls.mainurl = url
            cls.Down(downlist=down_list)
        else:
            Bilibili.logger.info("all video download complete")


if __name__ == "__main__":
    Bilibili.Main()
