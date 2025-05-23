#THIS IS THE OFFICIAL VERSION OF THIS PROJECT

!pip install numpy pandas statsmodels tensorflow keras xgboost scikit-learn matplotlib streamlit  random

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBRegressor
import random
import tensorflow as tf

# ==== Cố định seed để tái lập kết quả ====
seed = 42
os.environ['PYTHONHASHSEED'] = str(seed)
np.random.seed(seed)
random.seed(seed)
tf.random.set_seed(seed)

# ==== Đọc dữ liệu ====
df = pd.read_excel("/kaggle/input/output1/Data system POC_11Nov2024(mod).xlsx", sheet_name="Data- refinitiv")
df_actual = pd.read_excel("/kaggle/input/output1/Data system POC_11Nov2024(mod).xlsx", sheet_name="Sheet2")

# ==== Xử lý dữ liệu ====
df["Date"] = pd.to_datetime(df["Date"])
df_actual["Date"] = pd.to_datetime(df_actual["Date"])
df.sort_values("Date", inplace=True)
df = df.fillna(df.mean(numeric_only=True))

df_actual["VND"] = (df_actual["VND"]
                    .astype(str)
                    .str.replace(" ", "")
                    .astype(float))

df.set_index("Date", inplace=True)

# ==== Định nghĩa lại cột với VND ở vị trí thứ 3 ====
features = ['FEDRATE', 'DXY', 'VND', 'OMOrate', 'SBVcentralrate']  # VND ở index = 2
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df[features])

# ==== Tạo hàm xử lý dữ liệu dạng sliding window ====
def create_sliding_window_data(data, window_size=20):
    X, y = [], []
    for i in range(window_size, len(data)):
        X.append(data[i-window_size:i, [0, 1, 3, 4]])  # exclude VND (index=2)
        y.append(data[i, 2])  # target là VND
    return np.array(X), np.array(y)

# ==== Hàm dự báo autoregressive bằng XGBoost ====
def xgb_autoregressive_forecast(scaled_data, df, scaler, n_days=7, window_size=20):
    X, y = create_sliding_window_data(scaled_data, window_size)
    X = X.reshape((X.shape[0], X.shape[1] * X.shape[2]))  # flatten

    split_index = np.where(df.index.year >= 2024)[0][0] - window_size
    X_train, y_train = X[:split_index], y[:split_index]

    # Huấn luyện mô hình XGBoost
    model = XGBRegressor(n_estimators=600, learning_rate=0.9, max_depth=10)
    model.fit(X_train, y_train)

    # Dự báo autoregressive
    forecast = []
    last_window = scaled_data[-window_size:].copy()

    for _ in range(n_days):
        input_data = np.delete(last_window, 2, axis=1)  # bỏ cột VND
        input_flat = input_data.reshape(1, -1)
        pred_scaled = model.predict(input_flat)[0]

        # Tạo dòng mới với VND dự báo tại cột index=2
        new_row = last_window[-1].copy()
        new_row[2] = pred_scaled
        last_window = np.vstack([last_window[1:], new_row])
        forecast.append(new_row)

    forecast = np.array(forecast)
    forecast_inversed = scaler.inverse_transform(forecast)[:, 2]  # lấy lại VND từ cột thứ 3
    return forecast_inversed

# ==== Gọi hàm dự báo ====
n_days = 7
xgb_pred = xgb_autoregressive_forecast(scaled_data, df, scaler, n_days=n_days, window_size=20)

# ==== Tạo mảng ngày tương ứng để hiển thị ====
forecast_dates = pd.date_range(start=df_actual["Date"].iloc[0], periods=n_days + 1, freq='D')[1:]


# ==== Hiển thị bảng kết quả ====
print("### 📊 Kết quả dự báo XGBoost:")
print("Ngày       | Dự báo   | Xu hướng | % Thay đổi")
print("-------------------------------------------")

for i in range(1, n_days):
    date_str = forecast_dates[i].strftime("%d-%m-%Y")
    prev_value = xgb_pred[i - 1]
    curr_value = xgb_pred[i]
    change_percent = ((curr_value - prev_value) / prev_value) * 100
    trend = "📈 Up" if curr_value > prev_value else "📉 Down"
    print(f"{date_str} | {curr_value:.2f} | {trend} | {change_percent:.2f}%")

# ==== Vẽ biểu đồ kết quả ====
plt.figure(figsize=(12, 6))
plt.plot(forecast_dates, df_actual["VND"][:n_days].values, label="Thực tế", color="blue")
plt.plot(forecast_dates, xgb_pred, label="XGBoost", linestyle="dashed", color="purple")
plt.xlabel("Ngày")
plt.ylabel("Tỷ giá VND-USD")
plt.title("Dự báo tỷ giá VND-USD (Autoregressive XGBoost - VND ở cột 3)")
plt.legend()
plt.grid(True)
plt.show()
