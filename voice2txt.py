#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 議事録作成ツール

import sys
import time
from pathlib import Path
import torch
from transformers \
	import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import os
import imageio_ffmpeg
import subprocess

# フォルダ内から、議事録を作成するファイルを捜索
def search_file(search_path):
	# 配下のファイル全て
	data = list(Path(search_path).glob('*.*'))
	# 出力
	data2 = []
	# ファイルをループ
	for i in data:
		tmp = str(i)
		if tmp.lower().endswith('.txt'):
			continue
		# 同名の .txt があれば除外
		txt_path = tmp.rsplit('.', maxsplit=1)[0] + '.txt'
		if txt_path in map(str, data):
			continue
		# 絶対パスにし文字列にし追加
		data2.append(str(i.resolve()))
	return data2

# 処理時間を表示
def print_running_time(start):
	# 全処理時間(秒)
	elapsed = int(time.time() - start)
	# 処理時間(時分秒)
	hours = elapsed // 3600
	minutes = (elapsed % 3600) // 60
	seconds = elapsed % 60
	# 表示
	print(f'{hours}時間{minutes}分{seconds}秒かかりました。')

def transcribe_audio(audioFile):
	# config
	model_id = 'kotoba-tech/kotoba-whisper-v2.2'
	torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
	device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
	model_kwargs = {"attn_implementation": "flash_attention_2"} if torch.cuda.is_available() else {}

	# load model
	model = AutoModelForSpeechSeq2Seq.from_pretrained(
		model_id,
		torch_dtype=torch_dtype,
		low_cpu_mem_usage=True,
		use_safetensors=True
	).to(device)

	processor = AutoProcessor.from_pretrained(model_id)

	pipe = pipeline(
		'automatic-speech-recognition',
		model=model,
		tokenizer=processor.tokenizer,
		feature_extractor=processor.feature_extractor,
		torch_dtype=torch_dtype,
		device=device,
		return_timestamps='segment',
		generate_kwargs={'max_new_tokens': 128}
	)

	# run inference
	print('推論を開始します。')
	result = pipe(audioFile)
	return result['chunks']

# 'imageio-ffmpeg'がDLした'ffmpeg'のパスを取得して'PATH'に追加 
def get_ffmpeg_path():
	ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
	os.environ['PATH'] \
		= os.path.dirname(ffmpeg_path) \
		+ os.pathsep \
		+ os.environ['PATH']

# テキストファイルを作成しアウトプット
def make_txt(txtList, fileName):
	with open(fileName, 'w', encoding='utf-8') as file:
		# リストをループ
		for chunk in txtList:
			# 書き込み
			file.write(chunk['text'] + '\n')

# 音声ファイルをWhisper推奨フォーマット(16kHz, mono, 16bit WAV)に変換する。
def conv_audio(inputFile, outputFile):
	cmd = [
		"ffmpeg",
		"-i", inputFile,
		"-ar", "16000",        # サンプリングレート 16kHz
		"-ac", "1",            # モノラル
		"-c:a", "pcm_s16le",   # コーデック指定（16bit リトルエンディアン PCM）
		outputFile
	]
	print('推論用の中間ファイルを生成します。')
	subprocess.run(cmd)
	print('生成が完了しました。')

# ファイルを削除する。
def rmFile(fileName):
	os.remove(fileName)

def main(folder_path):
	try:
		# 現在時刻
		start_time = time.time()

		# 対象ファイルのリスト
		list = search_file(folder_path)

		# 'huggingface_hub'の'symlink warnings'の表示をOFFへ
		os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
		# ffmpegの環境変数設定
		get_ffmpeg_path()

		for item in list:
			# 変数
			wavFile = os.path.join(os.path.dirname(item), 'tmp.wav')
			txtFile = item.rsplit('.', maxsplit=1)[0] + '.txt'
			# 変換
			conv_audio(item, wavFile)
			# 推論
			make_txt(transcribe_audio(wavFile), txtFile)
			# 削除
			rmFile(wavFile)
		print('*****************************')
		print('処理が終了しました。')
		print_running_time(start_time)
		print('*****************************')
		# コマンドプロンプトを残す。
		input('エンターキーを押してください。')

	except Exception as e:
		print(f'Error: {e}')
		# コマンドプロンプトを残す。
		input('エンターキーを押してください。')

if __name__ == '__main__':
	main('格納先')